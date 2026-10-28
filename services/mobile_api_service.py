"""Mobile app API service (Expo/React Native client).

Deployment topology (Render):
  - Service name: fantasygmlab-mobile-api
  - Entrypoint: uvicorn services.mobile_api_service:app --host 0.0.0.0 --port $PORT
  - GET  /health              — process liveness (no Supabase dependency)
  - GET  /ready               — Supabase config readiness (no secret values)
  - GET  /v1/me               — authenticated user + entitlement + saved-league cap
  - GET  /v1/founder/analytics — founder-only product analytics report (403 for
                                  anyone without a server-issued founder_ops claim)
  - POST /v1/e (alias: /v1/analytics/event)   — record one product analytics event (guest-allowed;
                                  see modules.launch_analytics.TRACKED_EVENTS)
  - POST /v1/me/link-sleeper  — link a Sleeper username onto the caller's profile (roster resolution)
  - GET  /v1/sleeper/leagues?username=x  — the Sleeper leagues behind a username (add-league picker)
  - POST /v1/leagues/save                — save a Sleeper league to the account (cap-enforced)
  - GET  /v1/leagues/{id}                — Sleeper league metadata
  - GET  /v1/leagues/{id}/users          — Sleeper league members
  - GET  /v1/leagues/{id}/rosters        — Sleeper league rosters
  - GET  /v1/leagues/{id}/team-profiles  — team name/owner/avatar per roster
  - GET  /v1/leagues/{id}/team-rankings  — power/franchise/draft-capital rank + standings per roster
  - GET  /v1/leagues/{id}/draft-center   — draft posture + league-wide decision/partner cards
  - GET  /v1/leagues/{id}/draft-picks    — every draft pick asset + its full valuation breakdown
  - GET  /v1/leagues/{id}/live-draft           — discover this league's Sleeper drafts (status/season/rounds)
  - GET  /v1/leagues/{id}/live-draft/{draft_id} — polled read-only live draft board snapshot
  - GET  /v1/leagues/{id}/my-team        — your own roster's suggested starters vs. bench
  - GET  /v1/leagues/{id}/my-team-needs  — Strength & Pressure / Position Groups / Biggest Need detail
  - GET  /v1/leagues/{id}/my-roster      — the signed-in user's own roster in this league
  - GET  /v1/players?ids=1,2,3           — minimal Sleeper player info by id
  - GET  /v1/leagues/{id}/rankings       — league-adjusted player rankings
  - GET  /v1/leagues/{id}/players/{id}/rank — one player's league-adjusted rank, looked up directly
  - GET  /v1/news                        — curated NFL fantasy news (injury/role/transaction/off-field)
  - GET  /v1/players/{id}/news           — recent news items matched to one player
  - POST /v1/leagues/{id}/trade-analyzer — real accept/decline/counter verdict for a proposed trade
  - GET  /v1/leagues/{id}/recap          — latest completed-week league recap
  - GET  /v1/leagues/{id}/history        — season transaction timeline (trades/waivers/picks) with retrospective grades
  - GET  /v1/leagues/{id}/alerts         — roster-relevant news alerts
  - POST /v1/leagues/{id}/alerts/read    — durably mark one alert read (RLS-scoped)
  - GET  /v1/players/{id}/quick-view     — season stats + bio for the player detail pop-up
  - GET  /v1/players/{id}/percentile-explorer — distribution + nearby players behind one stat tile
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
  - GET  /v1/portfolio              — cross-league standing/needs/opportunities, one row per saved league (Premium)
  - GET  /v1/portfolio/exposure     — which players the caller owns across saved leagues, with concentration (Pro)
  - GET  /v1/leagues-glance        — compact per-league cards (record, top add, top trade, news count, top need), 3-min cache (Premium)
  - GET  /v1/leagues/{id}/trade-hub — real trade ideas for the caller's roster
  - GET  /v1/leagues/{id}/managers/tendencies — one-line, evidence-backed tendency per manager (Premium)
  - GET  /v1/leagues/{id}/managers/{roster_id}/tendencies — one manager's full tendency profile + evidence (Premium)
  - GET  /v1/leagues/{id}/waivers   — roster-need-aware free-agent pool + FAAB guidance
  - POST /v1/feedback/verdict                   — 'Report a bad verdict': one fixed reason, privacy-safe
  - POST /v1/leagues/{id}/trade-outcomes        — record a shared trade for later "did this happen?" follow-up
  - GET  /v1/trade-outcomes/pending             — this user's shared trades ready to be asked about
  - POST /v1/trade-outcomes/{id}/answer         — record yes/no/didnt_send, or snooze with still_pending
  - GET  /v1/trade-outcomes/history             — this user's answered trades, with a quiet "how it
                                                   worked out" result folded in once computed (pull-based,
                                                   no push/popup — powers the mobile Trade History screen)
  - GET  /v1/preferences                        — cross-device display density + last-viewed league
  - POST /v1/preferences                        — partial update to those same preferences
  - GET  /v1/leagues/{id}/gm-stance             — the caller's remembered team strategy for this league
  - POST /v1/leagues/{id}/gm-stance             — set/update that stance (null strategy clears it)
  - GET    /v1/scouting/prospects                    — shared college prospect catalog + aggregate + my report + watchlist flag
  - POST   /v1/scouting/prospects/{id}/report        — upsert my own scouting grade/round projection/note
  - DELETE /v1/scouting/prospects/{id}/report        — remove my own scouting report
  - POST   /v1/scouting/watchlist/{id}                — follow a prospect (personal watchlist)
  - DELETE /v1/scouting/watchlist/{id}                — unfollow a prospect
  - GET  /v1/external/players/{id}/projections  — (static API key, not a user session) one
                                                    player's weekly projection for the external
                                                    content-posting bot — see docs/external-api-contract.md
  - GET  /v1/external/projections                — (static API key) the full week's projectable
                                                    slate, optionally filtered by position
  - GET  /v1/external/players/{id}/news         — (static API key) structured news evidence for
                                                    one player — source links, timestamps, supported
                                                    claims, confidence/corroboration, and a conservative
                                                    supersession signal — see docs/external-api-contract.md
  - GET  /v1/external/players/{id}/rating-history — (static API key) previous/current 0-99 overall
                                                    rating, delta, effective date, and a short honest
                                                    explanation, from the daily Supabase snapshot table
                                                    modules.player_rating_history writes — see
                                                    docs/external-api-contract.md
  - GET  /v1/external/players/{id}/week-result  — (static API key) one player's real completed-week
                                                    stat line (Sleeper box score + PPR/half/standard)
  - GET  /v1/external/recap                     — (static API key) the week's real top performers and
                                                    notable stat lines — see docs/external-api-contract.md
  - GET  /v1/external/trades/interesting        — (static API key) concrete 2-3 asset trades graded by
                                                    the app's own evaluator, with a daily rotation — see
                                                    docs/external-trades-interesting.md
  - GET  /v1/external/trades/interesting/{id}/share-card.png — (static API key) branded PNG for one item

Auth model: the mobile app signs the user in against Supabase directly
(same `auth.users` table as the web app) and sends the resulting access
token as `Authorization: Bearer <token>` on every request. This service
verifies that token against Supabase Auth (GoTrue `/auth/v1/user`) on each
request — it never sees a password and never holds the service-role key.
Profile/entitlement reads use the caller's own token so Postgres Row Level
Security (not this service) decides what they can see, matching the web
app's client-side Supabase usage.

The `/v1/external/*` routes are a separate, narrower exception: there is no
Supabase user behind an external bot, so those routes authenticate with one
static, shared API key (`FANTASYDESK_EXTERNAL_API_KEY`, see
`require_external_api_key` and docs/external-api-contract.md) instead of
`require_user` — that key never grants access to any other route in this
file, same boundary `services/fantasy_content.py`'s own separate content
token already draws for a different payload.

This service intentionally contains no fantasy-analytics logic of its own —
it is a thin JSON wrapper around the existing `modules.sleeper` data access
so the web app and mobile app share one engine.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import dataclasses
import functools
import hashlib
import json
import logging
import os
import re
import secrets
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

import pandas as pd
import requests

from modules import (
    free_tier_ledger,
    trade_eval_usage,
    account_store,
    app_config,
    auth_supabase,
    build_identity,
    canonical_player_ranking,
    college_scouting,
    community_shared_trades,
    community_trades,
    dashboard_engine,
    draft_assistant,
    draft_center_cards,
    espn_leagues,
    external_leagues,
    games,
    external_matchups,
    faab,
    founder_analytics,
    gm_plan,
    gm_targets,
    guess_the_player,
    guess_the_player_leaderboard,
    injury_ui,
    launch_analytics,
    league_calendar,
    league_format_context,
    league_history,
    league_glance,
    league_rankings,
    league_warmup,
    league_recaps,
    league_standings,
    league_storylines,
    league_value_settings,
    league_display,
    live_activity,
    live_draft,
    live_draft_trade_evaluator,
    manager_activity,
    manager_tendencies,
    matchup_what_if,
    matchup_win_probability,
    my_news,
    news as news_cache,
    news_intelligence,
    news_signal,
    nfl_schedule,
    trade_grade,
    player_awards,
    player_background_profile,
    player_eligibility,
    performance,
    portfolio_exposure,
    pick_flow,
    player_history,
    player_projections,
    percentile_explorer,
    player_quick_view,
    player_rating_history,
    player_state_authority,
    players_refresh_flight,
    playoff_simulator,
    premium,
    premium_benefits,
    push_tokens,
    push_triggers,
    rankings,
    record_signal,
    redis_cache,
    referrals,
    roster_needs,
    saved_leagues,
    share_card_renderer,
    share_recommendation_cards,
    sleeper,
    sleeper_budget,
    sleeper_leagues,
    startup_cold_path,
    stripe_billing,
    team_stance,
    team_streaks,
    team_trade_history,
    trade_analyzer_fit,
    trade_hub_engine,
    trade_hub_presentation,
    trade_ideas,
    trade_offer_analyzer,
    transaction_grades,
    verdict_assumptions,
    verdict_feedback,
    waivers_logic,
    weekly_box_scores,
)
from modules import public_dynasty_values
from modules import external_news_contract
from modules import external_interesting_trades, external_news_feed, news_identity, news_ingest
from modules import this_week
from modules import team_defense
from modules import idp_scoring
from modules import guillotine as guillotine_module
from modules import keepers as keepers_module
from modules.team_eval import (
    build_league_summary,
    get_team_vs_league,
    lineup_open_slots,
    refine_team_directions,
    suggest_optimal_lineup,
)
from modules.trade_analyzer_assembly import pick_asset_from_mapping, player_asset_from_mapping


SERVICE_NAME = "mobile-api"

# --- Observability -----------------------------------------------------
#
# Before this, an unhandled exception on this service produced only the
# generic {"ok": false, "error": "Request failed."} 500 body below — nothing
# was ever written anywhere a human could see it. Render captures a
# process's stdout/stderr into its own log viewer automatically, so a
# stdlib `logging` logger writing there is a zero-external-dependency fix:
# configuring it is enough to make every crash debuggable from the Render
# dashboard alone. `force=True` guards against a no-op if some import order
# already attached a handler to the root logger before this module loads.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("fantasygm.mobile_api")

# Sentry is a genuine *upgrade* on top of the stdout logging above, not a
# requirement — inert (no import attempted, no network call, no behavior
# change) unless a real SENTRY_DSN is supplied via env var. This is the one
# piece of this fix that needs a human step: creating a free Sentry
# project and setting SENTRY_DSN in Render (see render.yaml).
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        if not sentry_sdk.is_initialized():
            sentry_sdk.init(
                dsn=SENTRY_DSN,
                integrations=[StarletteIntegration(), FastApiIntegration()],
                environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
                # Error events only by default — request tracing is a paid-quota
                # cost this app doesn't need to opt into implicitly. Raise via
                # SENTRY_TRACES_SAMPLE_RATE if that changes later.
                traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            )
            logger.info("Sentry error reporting initialized.")
    except Exception:
        logger.exception("Sentry initialization failed; continuing without it.")


def _report_to_sentry(exc: BaseException) -> None:
    """Best-effort forward to Sentry; a no-op whenever SENTRY_DSN is unset."""

    if not SENTRY_DSN:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        logger.exception("Failed to report exception to Sentry.")


# --- Rate limiting -------------------------------------------------------
#
# Backed by Redis (see modules/redis_cache.py and docker-compose.yml's
# `redis` service) rather than an in-memory dict: mobile-api now runs
# multiple uvicorn worker processes (see docker-compose.yml's mobile-api
# comment), each with its own separate memory, so a per-process counter
# would silently turn a "limit requests per client per window" rule into
# "limit*N requests per client per window" — a correctness regression, not
# just a perf one. Redis is one shared counter every worker increments, so
# the effective limit stays exactly what RATE_LIMIT_*_MAX says regardless
# of worker count.
#
# Counter pattern: plain INCR + EXPIRE (set the TTL only on the first
# increment in a window — see hit() below) on a key namespaced by the
# window's own start timestamp. This doesn't need a Lua script to be
# correct: INCR is atomic on its own, so concurrent callers in the same
# window always get distinct, strictly-increasing counts (no lost
# increments), and because each window's key is unique (window_start is
# part of the key), a request that never gets around to setting EXPIRE
# (e.g. the process is killed between INCR and EXPIRE) only leaks that one
# already-dead key in Redis — it can never be reused by a later window, so
# there's no correctness exposure, just a tiny, self-limiting memory cost.
# A fixed window (vs. a sliding log) can still allow a short burst right at
# a window boundary — the same accepted tradeoff as before this migration.
#
# Fails OPEN on any Redis error: see modules/redis_cache.py's module
# docstring for why (this is an auxiliary system, not the main request
# path, matching this codebase's existing "never let an auxiliary system
# take the main path down" philosophy — e.g. Team Situation fetch
# failures). A Redis outage means rate limiting is simply off until it
# recovers, never a 500 on every request.
#
# Limits are deliberately two-tier rather than per-route: everything this
# service serves is either a cheap read (GET) or a comparatively expensive/
# mutating write (POST/PUT/PATCH/DELETE — trade analysis, alerts, push
# registration, watchlist writes, ...). Bucketing by HTTP method class
# covers all ~50 routes with one rule each instead of hand-tuning every
# endpoint, while still giving mutations the tighter budget they deserve.
# Both tiers are env-configurable so they can be tuned in production
# without a code change/redeploy... other than the redeploy Render already
# requires to pick up a new env var value (there is no live-reload path).
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").strip().casefold() not in {
    "0",
    "false",
    "no",
    "off",
}
RATE_LIMIT_GENERAL_MAX = int(os.environ.get("RATE_LIMIT_GENERAL_MAX", "120"))
RATE_LIMIT_GENERAL_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_GENERAL_WINDOW_SECONDS", "60"))
RATE_LIMIT_MUTATING_MAX = int(os.environ.get("RATE_LIMIT_MUTATING_MAX", "20"))
RATE_LIMIT_MUTATING_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_MUTATING_WINDOW_SECONDS", "60"))
_RATE_LIMIT_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Telemetry ingest has its own bucket. It used to share the 20/min "mutating"
# budget with trade analysis etc., so one active session (page_view + feature_use
# per tap, onboarding steps) tripped 429s: analytics events were silently dropped
# AND the user's real writes started failing. A separate, larger budget fixes both.
RATE_LIMIT_ANALYTICS_MAX = int(os.environ.get("RATE_LIMIT_ANALYTICS_MAX", "240"))
RATE_LIMIT_ANALYTICS_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_ANALYTICS_WINDOW_SECONDS", "60"))
_RATE_LIMIT_ANALYTICS_PATH = "/v1/analytics/event"
# Neutral alias for the same ingest: "/analytics/" in a URL is a common
# ad-blocker filter pattern, so current web/mobile clients post here instead.
# The legacy path stays for already-shipped builds. Both share one handler and
# one rate-limit bucket.
_ANALYTICS_INGEST_ALIAS_PATH = "/v1/e"
_RATE_LIMIT_ANALYTICS_PATHS = frozenset({_RATE_LIMIT_ANALYTICS_PATH, _ANALYTICS_INGEST_ALIAS_PATH})


class _RedisFixedWindowRateLimiter:
    """Per-key request counter over a fixed wall-clock window, shared across
    every mobile-api worker process via Redis — see this section's module
    comment above for the counter pattern and fail-open behavior.
    """

    def hit(self, key: str, limit: int, window_seconds: int) -> tuple[bool, float]:
        now = time.time()
        window_start = (now // window_seconds) * window_seconds
        redis_key = f"ratelimit:{key}:{int(window_start)}:{window_seconds}"
        try:
            client = redis_cache.get_redis_client()
            count = client.incr(redis_key)
            if count == 1:
                # Only the caller who just created this window's key sets
                # its expiry — repeating EXPIRE on every hit would keep
                # pushing the key's death further out on sustained traffic,
                # turning this fixed window into a sliding one.
                client.expire(redis_key, window_seconds)
        except redis_cache.RedisError:
            logger.warning(
                "Redis unreachable for rate limiter key %s; failing open (request allowed).",
                key,
                exc_info=True,
            )
            return True, 0.0

        if count > limit:
            retry_after = max(0.0, window_seconds - (now - window_start))
            return False, retry_after
        return True, 0.0

    def reset(self) -> None:
        """Test-only: drop every tracked rate-limit counter so tests don't
        leak state across cases sharing one (fakeredis) instance."""
        try:
            client = redis_cache.get_redis_client()
            keys = list(client.scan_iter(match="ratelimit:*"))
            if keys:
                client.delete(*keys)
        except redis_cache.RedisError:
            pass


_rate_limiter = _RedisFixedWindowRateLimiter()


def _client_rate_limit_key(request: Request) -> str:
    """Bucket by client IP, further split by caller identity when present.

    Render terminates TLS behind a proxy, so the real client address is the
    first hop of X-Forwarded-For when present. A hash (not a decode/verify)
    of the raw Authorization header is enough to keep two different signed-in
    users behind the same IP/NAT from sharing one bucket — verifying the
    token is require_user's job, not this middleware's.
    """

    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else ""
    if not ip:
        ip = request.client.host if request.client else "unknown"
    authorization = request.headers.get("authorization", "")
    if authorization:
        fingerprint = hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:16]
        return f"{ip}:{fingerprint}"
    return ip


class _RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not RATE_LIMIT_ENABLED:
            return await call_next(request)
        # Never throttle the test suite by accident: hundreds of tests share
        # this one process/module and would otherwise pile onto the same
        # in-memory buckets within a single 60s window. The dedicated rate-
        # limit tests opt back in explicitly via DYNASTYGM_FORCE_RATE_LIMIT.
        if os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("DYNASTYGM_FORCE_RATE_LIMIT"):
            return await call_next(request)
        is_mutating = request.method.upper() in _RATE_LIMIT_MUTATING_METHODS
        limit = RATE_LIMIT_MUTATING_MAX if is_mutating else RATE_LIMIT_GENERAL_MAX
        window = RATE_LIMIT_MUTATING_WINDOW_SECONDS if is_mutating else RATE_LIMIT_GENERAL_WINDOW_SECONDS
        scope = "mutating" if is_mutating else "general"
        if is_mutating and request.url.path in _RATE_LIMIT_ANALYTICS_PATHS:
            limit, window, scope = RATE_LIMIT_ANALYTICS_MAX, RATE_LIMIT_ANALYTICS_WINDOW_SECONDS, "analytics"
        client_key = _client_rate_limit_key(request)
        # hit() calls the plain synchronous redis-py client (see
        # modules/redis_cache.py), which can block for up to
        # _SOCKET_CONNECT_TIMEOUT_SECONDS/_SOCKET_TIMEOUT_SECONDS (0.5s
        # each) if Redis is slow-but-reachable rather than cleanly down (the
        # RedisError fail-open path below only helps once an exception
        # actually surfaces). dispatch() runs directly on this worker's
        # asyncio event loop, so calling hit() inline here would stall every
        # other concurrent request on this worker for that long -- not just
        # the one being rate limited. asyncio.to_thread offloads the call to
        # a worker thread so a slow Redis only delays this one request.
        allowed, retry_after = await asyncio.to_thread(
            _rate_limiter.hit, f"{scope}|{client_key}", limit, window
        )
        if not allowed:
            logger.warning(
                "Rate limit exceeded: %s %s scope=%s",
                request.method,
                request.url.path,
                scope,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "error": "Too many requests. Please slow down and try again shortly.",
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )
        return await call_next(request)


_PLAYERS_CACHE_WARM_TIMEOUT_S = 60


def _warm_players_cache_at_startup() -> None:
    """Best-effort: populate rankings.load_players' process cache before
    this process starts accepting any traffic (see the lifespan below).

    Without this, the first real requests after a fresh deploy correctly
    single-flight onto ONE cold rankings.load_players() call (~5s locally,
    longer under real load/network) instead of each redoing that work —
    but every OTHER concurrent request still has to wait for that one
    call, and a real user's app opening right after a deploy can fire a
    dozen-plus of those at once. Doing this once here, before Render ever
    considers the deploy healthy enough to receive real traffic, moves
    that cost into the deploy's own already-expected, already-invisible
    startup window instead of onto whoever happens to open the app first.

    Bounded by a timeout rather than blocking forever: if this hangs (a
    genuine network outage reaching Sleeper, say), the process still
    starts and falls back to today's per-request load-or-build behavior
    rather than wedging the deploy indefinitely.
    """

    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("DYNASTYGM_TEST_MODE"):
        return
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="dgm-startup-cache-warm")
    future = executor.submit(rankings.load_players, PLAYERS_DB_PATH)
    try:
        future.result(timeout=_PLAYERS_CACHE_WARM_TIMEOUT_S)
    except Exception:
        pass
    # Not wait=True: if the timeout above fired, the load is still running
    # in the background — let it finish on its own time and populate the
    # (shared, module-level) cache whenever it completes, rather than
    # blocking process startup on it a second time here.
    executor.shutdown(wait=False)


def _enable_background_sleeper_players_refresh() -> None:
    """Serve an aged sleeper_players.json while one thread re-downloads it.

    Before this, the first request after the 5-minute TTL lapsed downloaded
    Sleeper's ~16MB dump inline (in every worker that hit it). Same test
    gate as _maybe_schedule_players_refresh: a background thread making
    live requests.get calls would collide with tests' requests mocks.
    """

    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("DYNASTYGM_TEST_MODE"):
        return
    sleeper.PLAYERS_BACKGROUND_REFRESH = True


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _enable_background_sleeper_players_refresh()
    _warm_players_cache_at_startup()
    yield


app = FastAPI(
    title="FantasyDesk Mobile API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=_lifespan,
)
# Full-league JSON payloads (rankings, draft-picks, trade-hub) are pandas-derived
# and can run into the hundreds of KB uncompressed — this app is consumed
# entirely over mobile networks, where that's real latency, not just bytes.
# 1KB minimum so tiny responses (health checks, single-player lookups)
# aren't paying gzip's per-request CPU cost for no bandwidth benefit.
app.add_middleware(GZipMiddleware, minimum_size=1024)


class _EspnLeagueRouteGate:
    """Refuses Sleeper-only features for ESPN leagues, in one place.

    ESPN leagues (league_id "espn:{id}:{season}", modules.espn_leagues) can
    serve only the routes in espn_leagues.ESPN_SUPPORTED_LEAGUE_ROUTES. Any
    other /v1/leagues/{espn key}/... request gets a 409 with a stable
    `reason` ("espn_not_supported") and the message clients show, instead of
    running a Sleeper-only engine on empty data. Pure ASGI (no
    BaseHTTPMiddleware) so non-ESPN requests pay one string check. Added
    before CORSMiddleware so the refusal still carries CORS headers."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") == "http"
            and scope.get("method") != "OPTIONS"
            and any(prefix in (scope.get("path") or "") for prefix in external_leagues.PREFIXES)
            and external_leagues.gated_league_path(scope.get("path") or "")
        ):
            response = JSONResponse(status_code=409, content=external_leagues.not_available_payload(scope.get("path") or ""))
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


app.add_middleware(_EspnLeagueRouteGate)
# Added after GZip so it wraps outermost and runs before any other work
# (including gzip'ing a response nobody should have gotten) on a throttled
# request.
app.add_middleware(_RateLimitMiddleware)
# The Next.js web frontend (web-next/) calls this API directly from the
# browser, which the Expo/React Native client never needed — RN requests
# aren't subject to CORS. Local dev always needs http://localhost:3000;
# WEB_APP_ORIGINS adds the deployed web app's real origin(s) (comma
# separated) without hardcoding a production hostname here. No origins
# configured beyond localhost is still safe: every route stays behind its
# existing auth/rate-limit middleware regardless of Origin.
_WEB_APP_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("WEB_APP_ORIGINS", "").split(",")
    if origin.strip()
] + ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_WEB_APP_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    if exc.status_code >= 500:
        # A deliberately-raised 5xx (e.g. "Accounts are not configured.") is
        # still a production problem worth seeing, just not a Python
        # traceback — no exc_info here since there isn't one.
        user_id = getattr(request.state, "user_id", None)
        logger.warning(
            "HTTP %s on %s %s (user_id=%s): %s",
            exc.status_code,
            request.method,
            request.url.path,
            user_id or "anonymous",
            detail,
        )
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": detail})


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"ok": False, "error": "Invalid request."})


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # The one thing this fix exists for: before this, a production 500 left
    # zero trace anywhere. Full traceback + request path + caller identity
    # (when known — require_user stashes it on request.state) now goes to
    # stdout, which Render already captures into its log viewer, before the
    # client-facing response (unchanged) is returned.
    user_id = getattr(request.state, "user_id", None)
    logger.error(
        "Unhandled exception on %s %s (user_id=%s)",
        request.method,
        request.url.path,
        user_id or "anonymous",
        exc_info=exc,
    )
    _report_to_sentry(exc)
    return JSONResponse(status_code=500, content={"ok": False, "error": "Request failed."})


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "health": "/health",
        "ready": "/ready",
        "me": "/v1/me",
    }


def _with_sleeper_as_of(fn):
    """Adds `sleeper_data_as_of` (ISO time of the OLDEST last-known Sleeper
    payload served) to a dict response ONLY when a 429/timeout/paused refresh
    made this request fall back to last-known data. Absent on live data, so
    clients that ignore it are unaffected (no UI change)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        sleeper_budget.begin_request()
        result = fn(*args, **kwargs)
        as_of = sleeper_budget.stale_as_of()
        if as_of and isinstance(result, dict):
            result = {**result, "sleeper_data_as_of": as_of}
        return result

    return wrapper


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only — must not depend on Supabase reachability.

    Also piggybacks the same stale-while-revalidate players refresh
    require_user triggers for authenticated requests (see
    _maybe_schedule_players_refresh's docstring) — this endpoint needs no
    auth, so any external health check pinging it (e.g. an uptime monitor,
    see docs/SELF_HOSTED_MIGRATION.md's "Basic uptime monitoring" section)
    doubles as a reliable, traffic-independent freshness check:
    injury_status/score/rank no longer depend on a real user happening to
    hit an authenticated endpoint after the hourly Sleeper cache goes
    stale.

    `build` answers "is this actually running what I think it's running" —
    see modules/build_identity.py's docstring for why Render's own
    RENDER_GIT_COMMIT doesn't exist here and DYNASTYGM_BUILD (set by
    deploy/release_deploy.sh) stands in for it on the self-hosted box.

    `deployed_at` answers the related-but-different question "how stale is
    production relative to `origin/main`" — deploy/release_deploy.sh
    exports DYNASTYGM_DEPLOYED_AT right before `docker compose up -d`, the
    same way it exports DYNASTYGM_BUILD. The real production auto-deploy
    path, `fantasygmlab-autopull.timer` -> deploy/autopull.sh (see
    docs/SELF_HOSTED_MIGRATION.md section 5.7), lives on the box and isn't
    tracked in this repo — whether it exports these two the same way is a
    property of that script, not guaranteed here. This is deliberately a
    timestamp stored at deploy time, not a live GitHub API call from this
    endpoint — an operator compares it against `git log origin/main -1
    --format=%cI` by hand (or scripts that comparison) to see how far
    behind `main` this box is. Empty string means unknown: local dev, or a
    deploy that didn't export it (whether that's release_deploy.sh never
    having run, or autopull.sh not setting it).
    """

    _maybe_schedule_players_refresh()
    identity = build_identity.resolve_build_identity()
    return {
        "status": "ok",
        "build": identity.revision,
        "deployed_at": identity.deployed_at,
    }


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
        if sleeper_budget.over_soft_threshold():
            # Background refresh pauses while Sleeper budget is tight; the
            # next request re-checks, and the on-disk copy keeps serving.
            sleeper_budget.note_deferred()
            return
        if not startup_cold_path.sleeper_players_cache_stale():
            return
        session_state: dict[str, Any] = {startup_cold_path.PLAYERS_REFRESH_PENDING_KEY: True}
        players_refresh_flight.schedule_deferred_players_refresh(
            db_path=PLAYERS_DB_PATH,
            # Out-of-process, not rankings.build_players_table directly: this
            # service is a single always-on instance, and the in-process
            # rebuild (real CPU work normalizing/scoring ~1700-2000 players)
            # was found to hold the GIL long enough to produce periodic p95
            # latency spikes (15-18+ seconds) for every other in-flight
            # request. A subprocess can't contend for this process's GIL no
            # matter how long the rebuild takes. See
            # modules.players_refresh_flight.build_players_table_out_of_process.
            build_players_table_fn=players_refresh_flight.build_players_table_out_of_process,
            session_state=session_state,
            pending_key=startup_cold_path.PLAYERS_REFRESH_PENDING_KEY,
            background=True,
        )
    except Exception:
        pass


def require_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
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
    # Stashed only for the unhandled-exception logger above to attribute a
    # crash to a caller — never read back by any endpoint's own logic.
    user_id = normalized.get("id")
    if user_id:
        request.state.user_id = user_id
        if SENTRY_DSN:
            try:
                import sentry_sdk

                sentry_sdk.set_user({"id": user_id})
            except Exception:
                pass
    _maybe_schedule_players_refresh()
    return normalized


def optional_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any] | None:
    """Same Supabase verification as require_user, but degrades to None
    instead of raising for a missing header, an invalid/expired token, or an
    unconfigured Supabase backend.

    POST /v1/analytics/event is the first endpoint on this service that must
    accept both authenticated and fully anonymous/guest callers on the same
    request path (most of modules.launch_analytics.TRACKED_EVENTS are
    guest/pre-auth events — landing_viewed, guest_*, signup_started, etc.),
    so require_user's hard 401/503 doesn't fit. Still populates
    request.state.user_id / Sentry user context when a session IS present,
    same as require_user, so crash attribution stays consistent either way.
    Deliberately skips require_user's _maybe_schedule_players_refresh() side
    effect — analytics pings have nothing to do with players.db freshness.
    """

    value = (authorization or "").strip()
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    token = token.strip()
    try:
        config = auth_supabase.get_supabase_config()
        if not auth_supabase.is_configured(config):
            return None
        user, _error = auth_supabase.fetch_auth_user(config, token)
    except Exception:
        return None
    if not user:
        return None
    normalized = auth_supabase.normalize_auth_user(user, access_token=token)
    normalized["_access_token"] = token
    user_id = normalized.get("id")
    if user_id:
        request.state.user_id = user_id
        if SENTRY_DSN:
            try:
                import sentry_sdk

                sentry_sdk.set_user({"id": user_id})
            except Exception:
                pass
    return normalized


# coridian_, 2026-10-19: real reported site-wide load-time complaint
# (separate regression already fixed for account_store.fetch_saved_leagues
# -- see _fetch_saved_leagues_cached above). Auditing every authenticated
# endpoint's own round trips turned up a second, much larger instance of
# the same class of gap: _fetch_profile_fields had NO cache at all despite
# being called from ~20 different endpoints (every one of them, not just
# the 14 that also call _resolve_my_roster) -- meaning essentially every
# authenticated request on this API paid a full uncached Supabase round
# trip just to read entitlement/sleeper_username. Same short-TTL
# single-flight cache as saved_leagues: this data only changes on a
# deliberate action (a Stripe/RevenueCat webhook, a username relink), both
# of which already have their own real propagation latency, so a brief
# cache window is invisible in practice.
_PROFILE_FIELDS_TTL_SECONDS = 15


def _fetch_profile_fields(config: dict, user_id: str, access_token: str) -> dict[str, str]:
    cache_key = redis_cache.build_cache_key("profile_fields", user_id)
    try:
        fields = redis_cache.redis_single_flight_cache(
            cache_key=cache_key,
            ttl_seconds=_PROFILE_FIELDS_TTL_SECONDS,
            compute=lambda: _fetch_profile_fields_uncached(config, user_id, access_token),
        )
    except Exception:
        fields = _fetch_profile_fields_uncached(config, user_id, access_token)
    # Sleeper call-rate budget priority (modules.sleeper_budget): paid tiers
    # always proceed; free-tier requests serve last-known data once the soft
    # threshold is crossed. A profile read that failed ("error") is not
    # proof of a free user, so it is left untagged (never deferred).
    try:
        if isinstance(fields, dict) and fields.get("status") == "ok":
            sleeper_budget.set_request_tier(fields.get("entitlement"))
    except Exception:
        pass
    return fields


_TRIAL_COLUMN_MISSING = False


def _fetch_profile_fields_uncached(config: dict, user_id: str, access_token: str) -> dict[str, str]:
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
    global _TRIAL_COLUMN_MISSING
    headers = auth_supabase.auth_headers(config, access_token)

    def _get(select: str):
        return requests.get(
            auth_supabase.rest_api_url(config, "profiles", f"select={select}&user_id=eq.{user_id}"),
            headers=headers,
            timeout=15,
        )

    try:
        # trial_ends_at is display-only (docs/supabase_free_trial.sql); if that
        # migration is not applied yet, fall back to the original select and
        # remember it so we do not pay a failed request on every profile read.
        if _TRIAL_COLUMN_MISSING:
            response = _get("entitlement,sleeper_username")
        else:
            response = _get("entitlement,sleeper_username,trial_ends_at")
            if response.status_code >= 400:
                _TRIAL_COLUMN_MISSING = True
                response = _get("entitlement,sleeper_username")
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
        # The old `entitlement in {"free", "premium"} else "free"`
        # whitelist here silently coerced "front_office" (the top paid
        # tier modules/stripe_webhook.py writes on a real Front Office
        # purchase — see modules.premium's FREE/PRO/FRONT_OFFICE tiers) to
        # "free", wiping out every premium benefit for that customer.
        # Normalize via modules.premium.canonical_tier first so any raw/
        # legacy stored value maps correctly, then collapse PRO and
        # FRONT_OFFICE to the wire value "premium" both this endpoint's
        # callers (web-next's `entitlement: "free" | "premium"` type,
        # mobile's equivalent) and every `is_at_least(entitlement, PRO)`
        # check in this file already expect — front_office-specific
        # capabilities (modules.premium.has_cross_league_exposure etc.)
        # aren't gated anywhere on this API yet, so there's nothing lost by
        # not exposing a third wire value until a caller actually needs it.
        normalized_tier = premium.canonical_tier(row.get("entitlement"))
        return {
            "entitlement": "premium" if normalized_tier != premium.FREE else "free",
            "sleeper_username": str(row.get("sleeper_username") or "").strip(),
            "trial_ends_at": str(row.get("trial_ends_at") or "").strip(),
            "status": "ok",
        }
    # No row found (e.g. profile bootstrap hasn't run yet) is a real, known
    # state — not an error — so a brand new user isn't shown a false alarm.
    return {"entitlement": "free", "sleeper_username": "", "status": "ok"}


# Mirrors modules.premium_benefits.MOBILE_PREMIUM_BENEFIT_LINES exactly — used only
# if that module raises (e.g. a future edit desyncs it from PREMIUM_INCLUDED_NOW),
# so /v1/me still returns something rather than a 500. Mobile has its own
# equivalent hardcoded fallback in PaywallScreen.tsx for when the request itself
# fails, so this is strictly a server-side belt-and-suspenders default.
_FALLBACK_PREMIUM_BENEFIT_LINES = [
    "Your full Next Move briefing, not just the top 4",
    "League Pulse leaders in the mobile app — the league’s top contender, rebuilder, draft capital, and most active manager",
    "The complete waiver board — stash candidates, watchlist depth, and a FAAB shortlist",
    "Every Trade Hub idea, not just the first 2",
    "GM Targets watchlist up to 50 players (Free is capped at 3)",
    "Portfolio — your record, rank, and top need across every saved league, not just one",
]


def _premium_benefit_lines() -> list[str]:
    try:
        lines = premium_benefits.mobile_premium_benefit_lines()
        return lines if lines else list(_FALLBACK_PREMIUM_BENEFIT_LINES)
    except Exception:
        return list(_FALLBACK_PREMIUM_BENEFIT_LINES)


def _premium_comparison_rows() -> list[dict[str, str]]:
    try:
        return premium_benefits.premium_comparison()
    except Exception:
        return []


def _founder_analytics_capable(user: dict[str, Any]) -> bool:
    """True only when the caller's own Supabase Auth app_metadata carries
    `founder_ops: true`.

    Same server-issued capability contract as
    modules.founder_ops.server_issued_capability (the Streamlit "Founder
    Ops" page's authorization): app_metadata is issued by Supabase Auth and
    settable only via the Supabase Admin Auth API, never through a user's
    own profile/user-metadata edits, so this cannot be forged client-side.
    `user` is always the dict `require_user` already returned for this
    request — its `app_metadata` already merges GoTrue's `user.app_metadata`,
    Postgres `raw_app_meta_data`, and the access token's own `app_metadata`
    claim (see auth_supabase.normalize_auth_user / canonical_app_metadata),
    so no extra Supabase round trip is needed here.
    """

    metadata = user.get("app_metadata")
    return isinstance(metadata, dict) and metadata.get("founder_ops") is True


@app.get("/v1/founder/analytics")
def get_founder_analytics(
    window: str = "7d",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Founder-only product analytics report — session/signup/feature-
    adoption rollups plus the "storage honesty" flag (durable Supabase table
    vs. host-local-JSONL-fallback-only), for the handful of accounts with a
    server-issued `founder_ops` capability claim (see
    _founder_analytics_capable above). Every other caller gets a real 403,
    not an empty/filtered report — this is an internal-analytics boundary,
    not a UX nicety.

    Delegates all aggregation to modules.founder_analytics.build_report —
    the same read path the Streamlit app would use — so web-next and any
    future client share one analytics engine instead of recomputing it here.
    """

    if not _founder_analytics_capable(user):
        raise HTTPException(status_code=403, detail="Not authorized.")
    valid_windows = {key for key, _label, _seconds in founder_analytics.WINDOWS}
    window_key = window if window in valid_windows else "7d"
    report = founder_analytics.build_report(window_key=window_key)
    return {"ok": True, "report": report}


class AnalyticsEventRequest(BaseModel):
    """Body for POST /v1/analytics/event.

    `event` must already be a canonical name from
    modules.launch_analytics.TRACKED_EVENTS (anything else is a no-op, same
    allowlist discipline track_event itself already enforces). `anon_id` is
    minted and persisted client-side (web-next's lib/analytics.ts, mobile's
    equivalent) — this service has no server-side session object to
    mint-once-and-persist into the way
    modules.launch_analytics.anonymous_id() does for Streamlit's
    `st.session_state` (see that function's docstring). `once_key` is an
    OPAQUE per-call dedup hint the client supplies (e.g. a league id) — see
    record_analytics_event for why this endpoint always re-scopes it before
    handing it to track_event.
    """

    event: str
    props: dict[str, Any] | None = None
    anon_id: str
    once_key: str | None = None
    # Real per-visit session id (web-next's getOrCreateSessionId: a
    # localStorage-backed, TTL'd id distinct from the durable anon_id) —
    # optional so older clients / mobile keep working unchanged (session_key
    # then falls back to anon_id, today's behavior).
    session_id: str | None = None


@app.post("/v1/e")
@app.post("/v1/analytics/event")
def record_analytics_event(
    body: AnalyticsEventRequest,
    request: Request,
    user: dict[str, Any] | None = Depends(optional_user),
) -> dict[str, bool]:
    """Product analytics ingestion for web-next/mobile — the only caller of
    modules.launch_analytics.track_event/track_page_view from this service.

    The real bug this closes: analytics_events had zero rows despite real
    user traffic, because neither web-next nor mobile ever called into
    modules.launch_analytics at all — its only existing caller was the
    legacy Streamlit app.py, which current users (web-next on
    fantasydesk.app, the mobile app) don't hit anymore. That module's
    track_* functions expect a Streamlit-session-state-shaped `state` dict
    (anonymous_id()/hash_account_id() read/write specific keys on it, e.g.
    to mint-once-and-persist a stable anon id across reruns in the same
    browser tab) — a stateless FastAPI request has no equivalent. This
    endpoint builds that shape fresh per request (the "shim") from the
    caller's own client-generated anon_id plus, when present, their verified
    Supabase user id, then calls straight into the existing, already-tested
    track_event/track_page_view so their dedup/account-hashing/
    ROUTE_EVENT_MAP/internal-traffic-exclusion logic is reused unchanged
    instead of re-implemented here.

    Deliberately permissive of anonymous callers (`Depends(optional_user)`,
    not `require_user`) — most of TRACKED_EVENTS are guest/pre-auth events
    (landing_viewed, guest_*, signup_started, ...), and requiring auth here
    would silently drop every one of them.

    Fail-soft by contract, like every other launch_analytics write path: an
    unrecognized event, a malformed/missing anon_id, or any internal error
    here returns `{"ok": False}` rather than ever raising — an analytics
    ping must never fail a real user-facing request.

    Bot/crawler traffic: a known crawler/bot/scripted-client User-Agent (see
    modules.launch_analytics.is_bot_user_agent) is dropped before anything is
    written — it never reaches track_event/track_page_view, so it cannot
    inflate event_count, sessions, or any other Founder Analytics count. A
    crawler using a generic/browser-like User-Agent is instead caught at
    report time by modules.founder_analytics._filter_bot_like_sessions.
    """

    try:
        if launch_analytics.is_bot_user_agent(request.headers.get("user-agent", "")):
            return {"ok": False}
        event_name = launch_analytics.normalize_event_name(str(body.event or "").strip())
        if event_name not in launch_analytics.TRACKED_EVENTS:
            return {"ok": False}
        anon_id = str(body.anon_id or "").strip()
        if not anon_id:
            return {"ok": False}
        raw_props = dict(body.props) if isinstance(body.props, dict) else {}
        # Platform split for the founder dashboard: web clients historically
        # sent none, so a missing/unknown value means "web".
        platform = str(raw_props.get("platform") or "").strip().casefold()
        raw_props["platform"] = platform if platform in launch_analytics.CLIENT_PLATFORMS else "web"

        user_id = str((user or {}).get("id") or "").strip()
        state_shim: dict[str, Any] = {launch_analytics.SESSION_ANON_KEY: anon_id}
        session_id = str(body.session_id or "").strip()[:64]
        if session_id:
            state_shim[launch_analytics.SESSION_REAL_ID_KEY] = session_id
        if user_id:
            state_shim["auth_session"] = {"user_id": user_id}
            # Real entitlement at event time (was always the "free" default:
            # this endpoint never looked a profile up at all). Reuses the
            # same cached (15s TTL) profile read every other authenticated
            # endpoint on this service already uses — see
            # _fetch_profile_fields's own docstring/history. Fail-soft: any
            # lookup problem already fails closed to "free" inside that
            # helper, so this can never raise or block the event.
            access_token = str((user or {}).get("_access_token") or "")
            try:
                config = auth_supabase.get_supabase_config()
                profile = _fetch_profile_fields(config, user_id, access_token)
                entitlement_value = "trial" if _active_trial_end(profile) else str(
                    profile.get("entitlement") or "free"
                )
            except Exception:
                entitlement_value = "free"
            state_shim["account_profile"] = {"entitlement": entitlement_value}

        if event_name == "page_view":
            route = str(raw_props.get("route") or "").strip()
            if not route:
                return {"ok": False}
            launch_analytics.track_page_view(
                launch_analytics.canonical_route_slug(route),
                state=state_shim,
                source_surface=str(raw_props.get("source_surface") or "navigation"),
                extra={"platform": raw_props["platform"]},
                # Plain page_views are deduped per tab on the client; the
                # server's in-memory marker resets on every deploy.
                dedupe=False,
            )
            return {"ok": True}

        # Non-route events: build the same safe/pseudonymous context props
        # build_context_props already assembles for every other caller
        # (account_state, entitlement default, league_key, route,
        # source_surface, experiment flags), then forward whatever this
        # caller also sent in `props` on top.
        context_props = launch_analytics.build_context_props(
            state_shim,
            route=str(raw_props.get("route") or ""),
            source_surface=str(raw_props.get("source_surface") or "feature"),
            league_id=str(raw_props.get("league_id") or ""),
            extra=raw_props,
        )

        # The client-supplied once_key is opaque (e.g. a raw league id) and
        # must be scoped to THIS caller before reaching track_event, whose
        # dedup marker set (_SESSION_EMITTED) is one process-global set
        # shared by every request — an un-scoped once_key would let one
        # account's event permanently suppress every other account's
        # identical event.
        once_key = ""
        if body.once_key and body.once_key.strip():
            scope = launch_analytics.hash_account_id(user_id) if user_id else anon_id
            league_scope = launch_analytics.hash_league_id(str(raw_props.get("league_id") or ""))
            once_key = f"{scope}:{league_scope}:{event_name}:{body.once_key.strip()}"

        launch_analytics.track_event(
            event_name,
            props=context_props,
            once_key=once_key,
            state=state_shim,
        )
        return {"ok": True}
    except Exception:
        return {"ok": False}


def _active_trial_end(row: dict[str, Any]) -> str:
    """The trial end to show: only for a still-future end on a trialing/unknown
    status. A past date is never shown as an active trial."""

    raw = str(row.get("trial_ends_at") or "").strip()
    if not raw:
        return ""
    try:
        end = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return end.isoformat() if end > datetime.now(timezone.utc) else ""


@app.get("/v1/me")
def get_me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = {"entitlement": "free", "sleeper_username": "", "status": "ok"}
    if user_id:
        profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or ""))
    trial_ends_at = _active_trial_end({"trial_ends_at": profile.get("trial_ends_at")}) if profile.get("entitlement") != "free" else ""
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
            # ISO end of an in-progress free trial, "" otherwise. Display only.
            "trial_ends_at": trial_ends_at,
        },
        # Canonical Premium benefit copy — single source of truth is
        # modules.premium_benefits (PREMIUM_INCLUDED_NOW / MOBILE_PREMIUM_BENEFIT_LINES),
        # the same list web's Premium page renders. The mobile Paywall fetches
        # this instead of keeping its own independently-authored copy.
        "premium_benefits": _premium_benefit_lines(),
        # Structured Free-vs-Pro rows built from the enforced limits
        # (modules.premium_benefits.premium_comparison). Clients fall back to
        # a static copy of the same shape when this is empty or missing.
        "premium_comparison": _premium_comparison_rows(),
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
    "team_stance",
    "scouting_reports",
    "prospect_watchlist",
    "decision_memory_events",
    "decision_memory_baselines",
    "notification_read_state",
    "guess_the_player_streaks",
    "guess_the_player_name_match_streaks",
    "community_trade_reactions",
    "community_shared_trades",
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


class LinkSleeperUsernameRequest(BaseModel):
    sleeper_username: str


@app.post("/v1/me/link-sleeper")
def link_sleeper_username(
    body: LinkSleeperUsernameRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Link a Sleeper username onto the caller's `profiles` row.

    This is the one piece of onboarding the web app's launch flow already
    does (modules.account_ui.save_current_context -> account_store.
    upsert_profile) that neither this service's POST /v1/leagues/save nor
    any other existing endpoint performs: /v1/leagues/save only resolves a
    `roster_id` for the league row being saved, it never writes
    `profiles.sleeper_username` itself. Every roster-resolution helper in
    this file (`_resolve_my_roster`, used by GET .../my-roster and GET
    .../dashboard) reads that profile column, so without this endpoint a
    web-next user who signs in (including as an anonymous Supabase guest,
    the same path mobile's `signInAnonymously` uses) and imports a Sleeper
    username has no way to make Dashboard/My Team resolve "my roster" at
    all. Thin wrapper only — same `account_store.build_profile_payload` /
    `upsert_profile` call web already makes, no new business logic.
    """

    username = str(body.sleeper_username or "").strip()
    if not username:
        raise HTTPException(status_code=422, detail="sleeper_username is required.")

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    ok, error = account_store.upsert_profile(
        config,
        access_token,
        account_store.build_profile_payload(
            user_id=user_id,
            email=str(user.get("email") or ""),
            sleeper_username=username,
        ),
    )
    if not ok:
        return {"ok": False, "reason": "not_available", "error": error}
    return {"ok": True, "sleeper_username": username}


# Referral program (modules.referrals) — a complete, already-built system
# (per-user invite code/link, distinct-leaguemate connection tracking, a
# capped free-month GM Pro reward) that until now was only ever wired into
# the legacy Streamlit app.py, invisible to every web-next/mobile user. This
# exposes the exact same logic here, reusing modules.referrals as-is (no
# changes to its reward math or anti-abuse rules).
#
# app.py's own trigger for crediting a referral is not a separate "redeem"
# action — it's the moment `modules.sleeper_leagues.lookup_user_leagues`
# resolves successfully (status "ok" or "no_leagues"), right after the
# existing `sleeper_connected` analytics event (see app.py's
# `load_leagues_for_username` and modules/referrals.py's own
# "Wiring" docstring). GET /v1/sleeper/leagues below is this service's exact
# equivalent of that call, so an optional `referral_code` param there is
# where redemption is wired, not a new standalone endpoint — matching the
# real flow rather than inventing one.
#
# modules.referrals.handle_sleeper_connected expects a Streamlit-shaped
# mutable `session_state`; this service has no such durable per-session
# object (every request is stateless), so `_redeem_referral_code` builds one
# ephemeral dict per call from this request's own auth + a fresh read of the
# caller's own user_settings row, then throws it away. The web-next/mobile
# client is what holds the pending code across the gap between landing on a
# `?ref=` link and connecting Sleeper (captured client-side into
# localStorage the same way modules.referrals.capture_referral_code stashes
# it in session_state), and passes it back on that one call.
def _redeem_referral_code(*, user: dict[str, Any], config: dict, code: str) -> dict[str, Any]:
    clean_code = str(code or "").strip()
    if not clean_code:
        return {"attempted": False}
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    settings_row, _error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    session_state: dict[str, Any] = {
        referrals.PENDING_CODE_SESSION_KEY: clean_code,
        "auth_session": {"user_id": user_id, "access_token": access_token},
        "account_user_settings": settings_row,
    }
    error = referrals.handle_sleeper_connected(config=config, session_state=session_state)
    return {"attempted": True, "ok": not bool(error), "message": error}


@app.get("/v1/referrals/my-code")
def get_my_referral_code(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """This user's own shareable invite code/link, plus their current GM Pro
    reward status — how many distinct leaguemates have connected Sleeper
    through it, and how many free comp months that has earned so far.

    Read-only: reuses modules.referrals' pure encoding/state helpers (no
    core logic duplicated here) against this user's own user_settings row,
    the same table/row-ownership shape every other settings-backed endpoint
    on this service already reads (see get_community_preferences above).
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    code = referrals.referral_code_for_user(user_id)
    link = referrals.referral_link(user_id, base_url=app_config.app_base_url())
    settings_row, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        settings_row = {}
    program = referrals.program_state(settings_row)
    return {
        "ok": not bool(error),
        "code": code,
        "link": link,
        "connected_count": int(program.get("connected_count") or 0),
        "comp_months_granted": int(program.get("comp_months_granted") or 0),
        "comp_until": program.get("comp_until"),
        "comp_is_active": referrals.comp_is_active(settings_row),
        "comp_months_remaining_capacity": referrals.comp_months_remaining_capacity(settings_row),
        "referrals_per_comp_month": referrals.REFERRALS_PER_COMP_MONTH,
        "max_comp_months": referrals.MAX_COMP_MONTHS,
    }


# DEPRECATED (billing Phase 2, 2026-10-24): web-next now calls the Supabase
# Edge Functions billing-plans / create-checkout-session / billing-portal-session
# (docs/billing-on-supabase.md). These three routes are kept ONLY as the
# rollback path (web-next: NEXT_PUBLIC_BILLING_BACKEND=fastapi). Do not add
# features here; do not delete until the box no longer needs a Stripe key.
#
# All three billing endpoints below are thin wrappers around
# modules.stripe_billing's already-correct, already-unit-tested functions —
# the same ones modules/premium_benefits.py (Streamlit) has used all along.
# This is the first non-Streamlit caller of that module; no Stripe
# integration logic is reimplemented here, only an HTTP surface web-next
# can call. Every redirect URL below points at this app's own /premium
# page (not Streamlit's `?page=premium`), since that's the real page a
# web-next caller is on.
# coridian_, 2026-10-19: "go ahead and do that until we have enough
# features to segregate between pro and front office" -- Front Office's
# one real functional difference (unlimited saved leagues,
# modules.saved_leagues.max_leagues_for) now also applies to Pro, so it's
# no longer offered as a separate new-signup choice here. The single
# already-subscribed Front Office customer keeps their existing
# subscription untouched (nothing about an existing Stripe subscription
# changes just because checkout stops offering it); stripe_billing.
# TIER_FRONT_OFFICE and its price plumbing are left fully intact for when
# there's a real feature split to bring it back for.
_BILLING_PLAN_KEYS: tuple[tuple[str, str, str], ...] = (
    (stripe_billing.MONTHLY, stripe_billing.TIER_PRO, stripe_billing.MONTHLY),
    (stripe_billing.ANNUAL, stripe_billing.TIER_PRO, stripe_billing.ANNUAL),
)


_TRIAL_PROFILE_SELECTS = (
    "select=stripe_customer_id,stripe_subscription_id,stripe_subscription_status,revenuecat_app_user_id,trial_ends_at&limit=1",
    # Older schemas (docs/supabase_free_trial.sql / revenuecat migration not applied).
    "select=stripe_customer_id,stripe_subscription_id,stripe_subscription_status&limit=1",
    "select=stripe_customer_id,stripe_subscription_id&limit=1",
)


def _fetch_trial_profile(user: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Billing-history columns used for trial eligibility / trial end display.

    Tries progressively narrower selects so a not-yet-applied migration never
    breaks the page. Returns (row, ok); ok=False means the profile could not
    be read at all, which callers treat as "not eligible" (fail closed).
    """

    user_id = str(user.get("id") or "")
    if not user_id:
        return {}, False
    supabase_config = auth_supabase.get_supabase_config()
    for query in _TRIAL_PROFILE_SELECTS:
        rows, error = account_store.fetch_rows(
            supabase_config,
            str(user.get("_access_token") or ""),
            "profiles",
            user_id=user_id,
            extra_query=query,
        )
        if not error:
            return (dict(rows[0]) if rows and isinstance(rows[0], dict) else {}), True
    return {}, False


@app.get("/v1/billing/plans", deprecated=True)
def get_billing_plans(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Live Stripe pricing for the Premium page — never hardcoded here.

    stripe_billing.plan_display_details() always prefers real Stripe Price
    objects and only falls back to its own DEFAULT_PLAN_DETAILS constants
    on a lookup failure, so this can't silently drift from what Stripe
    actually charges, and can't break the page either.
    """

    config = stripe_billing.load_stripe_config()
    details = stripe_billing.plan_display_details(config)
    # Front Office is no longer in _BILLING_PLAN_KEYS (see that constant's
    # own comment) -- every plan here is Pro, so there's only one features
    # list to build, not a per-tier branch.
    features = premium_benefits.mobile_premium_benefit_lines()
    plans = []
    for detail_key, tier, interval in _BILLING_PLAN_KEYS:
        label, price, cadence = details.get(detail_key) or stripe_billing.DEFAULT_PLAN_DETAILS[detail_key]
        plans.append(
            {
                "tier": tier,
                "interval": interval,
                "label": label,
                "price": price,
                "cadence": cadence,
                "features": features,
            }
        )
    # Zach, 2026-10-19 ("we dont need renders publuishable" / "find a work
    # around" -- web-next isn't on Render, there's no NEXT_PUBLIC_ build
    # pipeline to add this to): served here at runtime instead, same place
    # the Premium page already fetches plan data from before a user can
    # even click Subscribe. Intentionally public/safe to ship to the
    # client (unlike the secret key, which never leaves this service).
    # Trial copy is shown only when this account can actually get the trial
    # (enabled + no prior billing history). Cheap profile check only here; the
    # checkout endpoint additionally checks Stripe by email.
    profile, profile_ok = _fetch_trial_profile(user)
    trial_eligible = profile_ok and stripe_billing.trial_eligible(
        config, tier=stripe_billing.TIER_PRO, profile=profile, check_stripe=False
    )
    return {
        "ok": True,
        "plans": plans,
        "stripe_publishable_key": config.publishable_key,
        "trial": {"days": config.trial_days if trial_eligible else 0, "eligible": bool(trial_eligible)},
    }


class CheckoutRequest(BaseModel):
    tier: str = stripe_billing.TIER_PRO
    interval: str = stripe_billing.MONTHLY
    # Where to land after a successful/canceled checkout, e.g. "/" to resume
    # onboarding instead of the standalone /premium page. Caller-supplied,
    # so only ever used as a path appended to this app's own app_base_url
    # (stripe_return_url never treats it as a full URL/host) — never a
    # redirect to an arbitrary external site.
    return_to: str = "/premium"
    # Zach, 2026-10-19: "We need to try to embed stripe so theres not a
    # million redirectes" — "hosted" (default) keeps the existing
    # redirect-to-checkout.stripe.com flow; "embedded" returns a
    # client_secret the frontend mounts in place via Stripe.js's
    # EmbeddedCheckout instead of leaving the app at all.
    ui_mode: str = "hosted"


def _safe_return_path(path: str) -> str:
    clean = str(path or "").strip()
    if not clean.startswith("/") or clean.startswith("//") or len(clean) > 200:
        return "/premium"
    return clean


def _verified_checkout_email(user: dict[str, Any]) -> str:
    """The signed-in account's own email, only when Supabase has verified it.

    Read from the GoTrue user the bearer token resolved to (never from the
    request body), so a client can't choose whose email Stripe prefills.
    Returns "" (no prefill) for a missing, malformed or unconfirmed email.
    """

    email = str(user.get("email") or "").strip()
    if not email or "@" not in email or len(email) > 254:
        return ""
    if not (user.get("email_confirmed_at") or user.get("confirmed_at")):
        return ""
    return email


@app.post("/v1/billing/checkout", deprecated=True)
def create_billing_checkout(
    body: CheckoutRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Start a real Stripe Checkout session for the signed-in caller.

    Hosted mode (default) returns the Stripe-hosted checkout URL to
    redirect the browser to. Embedded mode (body.ui_mode="embedded")
    instead returns a client_secret the frontend mounts in place via
    Stripe.js — either way, this app never collects card details itself.
    """

    user_id = str(user.get("id") or "")
    email = _verified_checkout_email(user)
    if not user_id:
        raise HTTPException(status_code=401, detail="Checkout requires a signed-in account.")
    config = stripe_billing.load_stripe_config()
    profile, profile_ok = _fetch_trial_profile(user)
    # An existing Stripe customer (from our own profile row, never the
    # client) is reused so Checkout shows its email; else customer_email.
    stripe_customer_id = str(profile.get("stripe_customer_id") or "").strip()
    trial_ok = profile_ok and stripe_billing.trial_eligible(
        config, tier=body.tier, email=email, profile=profile
    )
    return_path = _safe_return_path(body.return_to)
    embedded = str(body.ui_mode or "").strip().casefold() == "embedded"
    try:
        session = stripe_billing.create_checkout_session(
            config=config,
            user_id=user_id,
            email=email,
            customer_id=stripe_customer_id,
            interval=body.interval,
            tier=body.tier,
            trial_eligible=trial_ok,
            ui_mode="embedded" if embedded else "hosted",
            return_url=app_config.stripe_return_url(f"{return_path}?billing=success", base_url=config.app_base_url)
            if embedded
            else "",
            success_url=app_config.stripe_return_url(f"{return_path}?billing=success", base_url=config.app_base_url),
            cancel_url=app_config.stripe_return_url(f"{return_path}?billing=cancel", base_url=config.app_base_url),
        )
    except stripe_billing.BillingConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except Exception:
        # Zach, 2026-10-19: "502 stripe?" — this previously swallowed the
        # real exception entirely (`from None`, no logging), so a live
        # failure had no trail to diagnose from after the fact. Logged
        # (stdout + Sentry, if configured — see this file's own Sentry
        # init above) without changing the generic detail returned to the
        # caller, which still must never leak internal Stripe error text.
        logger.exception("Stripe checkout session creation failed for user_id=%s tier=%s interval=%s", user_id, body.tier, body.interval)
        raise HTTPException(status_code=502, detail="Could not start checkout.") from None

    if embedded:
        client_secret = str(getattr(session, "client_secret", "") or "")
        if not client_secret:
            raise HTTPException(status_code=502, detail="Could not start checkout.")
        return {"ok": True, "client_secret": client_secret}

    checkout_url = str(getattr(session, "url", "") or "")
    if not checkout_url:
        raise HTTPException(status_code=502, detail="Could not start checkout.")
    return {"ok": True, "checkout_url": checkout_url}


@app.post("/v1/billing/portal", deprecated=True)
def create_billing_portal(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Open the Stripe customer portal for an existing subscriber to manage
    or cancel. Needs `profiles.stripe_customer_id` — the same column
    modules/premium_benefits.py's existing "Manage Billing" button already
    reads (written by modules.stripe_webhook on a completed checkout), not
    a new lookup invented for this endpoint.
    """

    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Managing billing requires a signed-in account.")
    supabase_config = auth_supabase.get_supabase_config()
    rows, _error = account_store.fetch_rows(
        supabase_config,
        access_token,
        "profiles",
        user_id=user_id,
        extra_query="select=stripe_customer_id",
    )
    stripe_customer_id = ""
    if rows and isinstance(rows[0], dict):
        stripe_customer_id = str(rows[0].get("stripe_customer_id") or "").strip()
    if not stripe_customer_id:
        raise HTTPException(status_code=404, detail="No billing account found for this user yet.")
    config = stripe_billing.load_stripe_config()
    try:
        portal = stripe_billing.create_customer_portal_session(
            config=config,
            stripe_customer_id=stripe_customer_id,
            return_url=app_config.stripe_return_url("/premium", base_url=config.app_base_url),
        )
    except stripe_billing.BillingConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=502, detail="Could not open billing portal.") from None
    portal_url = str(getattr(portal, "url", "") or "")
    if not portal_url:
        raise HTTPException(status_code=502, detail="Could not open billing portal.")
    return {"ok": True, "portal_url": portal_url}


@app.get("/v1/sleeper/leagues")
def lookup_sleeper_leagues(
    username: str = "",
    referral_code: str = "",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """The Sleeper leagues behind a username, for the add-league picker.

    Read-only Sleeper lookup (modules.sleeper_leagues, the same function
    web's onboarding import uses) — saves nothing. Falls back to the
    caller's linked `profiles.sleeper_username` when none is supplied so
    the app can pre-populate the picker.

    `referral_code` (optional): this is also the real moment app.py credits
    a pending referral (see modules.referrals.handle_sleeper_connected's own
    docstring and the "Referral program" comment above
    link_sleeper_username) — a username resolving here, successfully or
    with no leagues, is exactly app.py's own `sleeper_connected` condition.
    The caller only sends this once, right after landing on a `?ref=` link.
    """

    config = auth_supabase.get_supabase_config()
    clean = str(username or "").strip()
    if not clean:
        user_id = str(user.get("id") or "")
        if user_id:
            profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or ""))
            clean = profile.get("sleeper_username") or ""
    if not clean:
        return {"ok": False, "status": "empty_username", "leagues": [], "username": "", "message": sleeper_leagues.league_lookup_customer_message("empty_username")}

    result = sleeper_leagues.lookup_user_leagues(clean)
    response: dict[str, Any] = {
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
    if referral_code and result.status in {"ok", "no_leagues"}:
        response["referral"] = _redeem_referral_code(user=user, config=config, code=referral_code)
    return response


class SaveLeagueRequest(BaseModel):
    league_id: str
    sleeper_username: str = ""
    league_name: str = ""
    make_default: bool = False
    # ESPN leagues only (league_id "espn:{id}:{season}"): the team the user
    # picked as theirs in the import step. Sleeper leagues resolve this
    # from the username instead.
    roster_id: str = ""


class EspnLeaguePreviewRequest(BaseModel):
    league_id: str
    season: int


@app.post("/v1/espn/leagues/preview")
def preview_espn_league(
    body: EspnLeaguePreviewRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Load a public ESPN league and show what importing it would give.

    Read-only (saves nothing): league name, every team (so the user can
    pick theirs), how many roster players matched FantasyDesk's player
    list, and which features work for ESPN leagues today
    (modules.espn_leagues.ESPN_FEATURE_SUPPORT). The returned
    `league.league_key` is what POST /v1/leagues/save takes as league_id.

    Public leagues only. This endpoint takes no espn_s2/SWID cookies, and a
    private league answers `private_league` (see modules.espn_leagues for
    why private leagues are out of scope). Everyday failures are a 200 with
    `ok: false` and a `reason`, like GET /v1/sleeper/leagues."""

    league_key = espn_leagues.build_espn_league_key(body.league_id, body.season)
    if not league_key:
        return {"ok": False, "reason": "invalid_input", "message": espn_leagues.ERROR_MESSAGES["invalid_input"]}
    try:
        snapshot = espn_leagues.load_league_snapshot(league_key)
    except espn_leagues.ESPNLeagueError as exc:
        return {"ok": False, "reason": exc.reason, "message": exc.message}
    # Saving right after previewing (the normal flow) reuses this load
    # instead of calling ESPN again.
    espn_leagues.store_snapshot(league_key, snapshot)
    return espn_leagues.preview_payload(snapshot)


class ImportLeaguePreviewRequest(BaseModel):
    platform: str
    league_id: str
    season: int


@app.post("/v1/import/preview")
def preview_imported_league(
    body: ImportLeaguePreviewRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Fleaflicker / MFL twin of POST /v1/espn/leagues/preview.

    Public leagues only: no credentials of any kind are accepted. Read-only
    (saves nothing); `league.league_key` is what POST /v1/leagues/save takes.
    `diagnostics.unmapped_players` lists, honestly, every rostered player that
    could not be matched to a FantasyDesk player id (those are left off the
    roster, never guessed)."""

    platform = str(body.platform or "").strip().lower()
    if platform not in external_leagues.IMPORT_PLATFORMS:
        raise HTTPException(status_code=422, detail="Unsupported league platform.")
    return external_leagues.preview_league(platform, body.league_id, body.season)


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

    is_espn = external_leagues.is_external_league_key(league_id)
    espn_roster_id = str(payload.roster_id or "").strip()
    if is_espn:
        # Same "verify before writing" rule as Sleeper below, against ESPN.
        espn_snapshot = external_leagues.get_league_snapshot(league_id)
        if not espn_snapshot:
            return {"ok": False, "reason": "league_not_found", "cap": 0}
        if external_leagues.mapping_blocks_import(espn_snapshot):
            return {"ok": False, "reason": "mapping_too_low", "cap": 0}
        if not any(str(roster.get("roster_id")) == espn_roster_id for roster in espn_snapshot["rosters"]):
            return {"ok": False, "reason": "espn_team_not_selected", "cap": 0}
        league = espn_snapshot["league"]
    else:
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

    if is_espn:
        # No Sleeper username on an ESPN row: it would make the Sleeper
        # season-rollover check treat this league as a Sleeper one.
        username = ""
        roster_id = espn_roster_id
    else:
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
    # The saved set just changed: drop the cached list (ESPN roster resolution
    # reads roster_id from this row, and the Free league cap counts saved
    # rows) and release any unsaved-league claim so the saved league REPLACES
    # it rather than adding a second allowed league.
    _forget_saved_leagues_cache(user_id)
    free_tier_ledger.release_league_claims(user_id)
    warming = False
    if not is_espn:
        warming = _start_league_warmup(user_id, league_id, roster_id)
    return {
        "ok": True,
        "reason": "",
        "cap": cap,
        "warming": warming,
        "league": {
            "league_id": league_id,
            "league_name": league_name,
            "is_default": is_default,
            "platform": external_leagues.league_platform(league_id),
        },
    }


def _build_warmup_steps(league_id: str, roster_id: Any) -> dict[str, Any]:
    """The same cached builders the Dashboard, My Team and Trade Hub call, at
    their defaults for a brand-new league (Dynasty lens, no declared Team
    Situation, no GM Targets), so the first real request is a cache hit."""

    lens = "Dynasty"

    def roster_step() -> None:
        sleeper.get_league(league_id)
        sleeper.get_rosters(league_id)

    def values_step() -> None:
        league_value_settings.build_valued_players_frame_cached(
            league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
        )
        league_rankings.build_league_rankings_frame_cached(
            league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
        )

    def trades_step() -> None:
        if roster_id in (None, ""):
            return
        league = sleeper.get_league(league_id) or {}
        if league_calendar.trade_deadline_passed(league):
            return
        trade_hub_engine.generate_trade_idea_records_cached(
            league_id=league_id,
            roster_id=int(roster_id),
            strategy=team_stance.team_strategy_for_stance(""),
            lens=lens,
            players_db_path=PLAYERS_DB_PATH,
            untouchable_player_ids=(),
            gm_target_player_ids=(),
            team_stance="",
        )

    return {"roster": roster_step, "values": values_step, "trades": trades_step}


def _start_league_warmup(user_id: str, league_id: str, roster_id: Any) -> bool:
    """Start the best-effort warm-up thread (low priority, off the request).
    start_warmup only does two Redis calls and a thread spawn, so it cannot
    hold up the save response. True means the status endpoint will report
    progress; False (rate-limited, busy, Redis down) means nothing to wait
    for. Never raises."""

    try:
        return bool(
            league_warmup.start_warmup(
                user_id=user_id,
                league_id=league_id,
                steps=_build_warmup_steps(league_id, roster_id),
            )
        )
    except Exception:
        logger.debug("league warm-up could not start", exc_info=True)
        return False


# Sleeper leagues only ever grow a "next season" successor once the
# current one is no longer being played -- see resolve_league_path_id's
# own cost-control note below for why this status set gates whether it's
# even worth attempting a live rollover check at all.
_STALE_LEAGUE_STATUSES = frozenset({"complete"})


def _candidate_sleeper_username_for_rollover(
    config: dict, access_token: str, user_id: str, profile: dict[str, str]
) -> str:
    """Best-effort Sleeper username to resolve a raw path `league_id`
    against (see resolve_league_path_id below). Prefers the signed-in
    caller's own linked (profile) username -- the common case, and exactly
    the one the real production repro used (save + link-sleeper, then hit
    a path param directly) -- and falls back to any of their saved_leagues
    rows' per-league username if the profile has none. Returns "" when the
    caller has never linked Sleeper at all (e.g. a brand-new account, or
    someone only ever viewing public league data with no Sleeper link of
    their own), in which case resolution is skipped entirely."""

    username = str(profile.get("sleeper_username") or "").strip()
    if username or not user_id:
        return username
    try:
        saved_rows, saved_error = _fetch_saved_leagues_cached(config, access_token, user_id)
    except Exception:
        return ""
    if saved_error or not saved_rows:
        return ""
    for row in saved_rows:
        candidate = str(row.get("sleeper_username") or "").strip()
        if candidate:
            return candidate
    return ""


def resolve_league_path_id(
    league_id: str,
    user: dict[str, Any] = Depends(require_user),
) -> str:
    """Shared FastAPI dependency for (almost) every `/v1/leagues/{league_id}`
    route below: resolves a raw path `league_id` forward across a Sleeper
    season rollover BEFORE the route body runs, reusing the exact same
    `resolve_saved_league_rollover` chain-walk (via `_resolve_league_rollover_
    cached`) PR #1312 already added for the saved-leagues LIST endpoint.

    Real production bug, 2026-10-21/22 (coridian_, live, confirmed with a
    disposable test account against production): PR #1312's resolution only
    ran inside `_fetch_saved_leagues_cached` -- i.e. when ENUMERATING a
    user's saved leagues. It never touched the ~40 OTHER endpoints that take
    `league_id` directly as a URL path parameter (my-roster, dashboard,
    trade-hub, waivers, matchup, etc.). A client navigating with a
    `league_id` it already had in hand from BEFORE a rollover was first
    noticed (a saved-league row fetched earlier, a deep link, cached local
    state) kept hitting every one of those endpoints with the stale id, with
    no resolution check at all -- e.g. GET .../my-roster/{stale_id} kept
    returning the prior season's roster verbatim, HTTP 200, no error.

    Needs a sleeper_username to resolve against; a raw incoming path doesn't
    carry one, so this borrows the signed-in caller's OWN linked username
    (see `_candidate_sleeper_username_for_rollover`) as the resolution
    candidate. This is deliberately safe even for a league_id the caller
    hasn't saved and doesn't belong to (e.g. public league data shared by a
    leaguemate's link): `resolve_current_season_league_id` only rewrites the
    id when that candidate username's OWN Sleeper leagues contain a REAL
    `previous_league_id` chain link back to this exact incoming id -- so for
    a league this caller has no real connection to, resolution is an
    unconditional no-op and the original id reaches the route unchanged,
    same as before this dependency existed.

    Fails open on every error path -- a missing link, a Supabase hiccup, an
    unreachable Sleeper API -- by returning the original `league_id`
    untouched; this must never turn a transport hiccup into a 500 or a wrong
    league on an otherwise-healthy request.

    NOT applied to several endpoints on purpose, each documented at its own
    route (grep this file for "NOT resolved" to find every one):
      - `DELETE /v1/leagues/{league_id}/save` -- removes a specific
        already-stored `saved_leagues` row by the exact id the client
        sent, which may still be the OLD, not-yet-migrated id; resolving
        forward would make the delete silently match nothing, leaving the
        stale row un-removable.
      - `POST /v1/leagues/{league_id}/alerts/read`, `POST .../trade-
        outcomes`, `POST/DELETE/PATCH .../gm-targets...`, `POST .../gm-
        stance`, `POST .../team-stance` -- each writes a row whose identity
        (or whose paired add/remove consistency) is keyed by the exact
        `league_id` the client sent. The matching GET/read side of each of
        these IS resolved, so a preference or watchlist entry written
        under a stale id simply self-heals the next time it's read back
        and re-declared under the current id -- never a wrong
        roster/matchup/trade-data result, never an error, never silently
        unflagged (every exclusion has an inline comment at its route).
        `alerts/read` additionally writes the resolved id's row itself and
        its GET reads both ids, so alert read state never self-heals by
        re-declaring -- it is simply shared across both ids.

    A handful of the READ endpoints this dependency DOES cover (Dashboard,
    Trade Hub, Trade Finder, GM Plan, the dedicated GM Stance/Team Stance/
    GM Targets GETs, ...) separately read those same league-scoped user
    preference tables, keyed by (user_id, league_id). Since those tables
    are NOT migrated forward on rollover the way `saved_leagues` is (see
    `_apply_league_rollover_resolution`), the first time a league's id
    resolves forward here, a preference set under the OLD id will briefly
    read back as unset/default until the caller re-declares it under the
    new id. Same known, documented, self-healing, low-severity side effect
    as above -- see the PR description for the follow-up to migrate those
    tables the same way `saved_leagues` already is.

    Cost control: resolution needs a live Sleeper leagues-list lookup for
    the candidate username, which is too expensive to pay on every single
    one of these ~40 endpoints' every single request. Sleeper only ever
    mints a "next season" successor for a league once that league is no
    longer being played, so this is gated on the INCOMING id's own league
    `status` first -- "pre_draft" / "drafting" / "in_season" cannot
    possibly be stale (no newer id can exist yet), so resolution is
    skipped with zero extra network calls for the overwhelming common
    case. Only a `status == "complete"` league (this season over, or
    already rolled over) pays the one extra, 24h-cached lookup.
    """

    league_id_clean = str(league_id or "").strip()
    if not league_id_clean:
        return league_id
    if external_leagues.is_external_league_key(league_id_clean):
        # ESPN league ids don't change between seasons, and the season is
        # part of the key, so there is nothing to resolve (and no reason to
        # load the league just to read a Sleeper status).
        return league_id_clean
    try:
        user_id = str(user.get("id") or "")
        if not user_id:
            return league_id_clean
        league = sleeper.get_league(league_id_clean)
        status = str((league or {}).get("status") or "").strip()
        if status not in _STALE_LEAGUE_STATUSES:
            return league_id_clean
        config = auth_supabase.get_supabase_config()
        access_token = str(user.get("_access_token") or "")
        profile = _fetch_profile_fields(config, user_id, access_token)
        sleeper_username = _candidate_sleeper_username_for_rollover(config, access_token, user_id, profile)
        if not sleeper_username:
            return league_id_clean
        resolved = _resolve_league_rollover_cached(league_id_clean, sleeper_username)
        return resolved or league_id_clean
    except Exception:
        return league_id_clean


FREE_LEAGUE_CAP_REASON = "free_league_cap"

_FREE_LEAGUE_CAP_UPSELL = {
    "title": "Your Free plan includes one league",
    "body": (
        "Free accounts keep one league. This one isn't it, so its data is "
        "locked. Upgrade to Premium to use all of your leagues."
    ),
}


class FreeLeagueLocked(Exception):
    """Raised by `require_league_access`; the handler below turns it into the
    standard locked payload (HTTP 200, like every other soft gate)."""

    def __init__(self, league_id: str) -> None:
        super().__init__(league_id)
        self.league_id = league_id


def free_league_locked_payload(league_id: str = "") -> dict[str, Any]:
    return {
        "ok": True,
        "reason": FREE_LEAGUE_CAP_REASON,
        "league_locked": True,
        "league_id": league_id,
        "is_premium": False,
        "upsell": dict(_FREE_LEAGUE_CAP_UPSELL),
    }


@app.exception_handler(FreeLeagueLocked)
async def _free_league_locked_handler(_request: Request, exc: FreeLeagueLocked):
    return JSONResponse(status_code=200, content=free_league_locked_payload(exc.league_id))


def _league_access_allowed(user: dict[str, Any], league_id: str) -> bool:
    """Free-tier league cap, ONE authority for every league-scoped endpoint
    (see `require_league_access`). Cheap: the profile and saved-leagues reads
    are the same per-user Redis single-flight caches the rest of the request
    uses; Pro/Front Office/trialing (entitlement is already PRO while a trial
    runs) needs only the profile. Fails open only on a transport error."""

    user_id = str(user.get("id") or "")
    if not user_id:
        return True
    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    profile = _fetch_profile_fields(config, user_id, access_token)
    if profile.get("status") == "error" or premium.is_at_least(profile.get("entitlement"), premium.PRO):
        return True
    saved_rows, saved_error = _fetch_saved_leagues_cached(config, access_token, user_id)
    if saved_error:
        return True
    return _free_league_allowed(user_id, profile, league_id, list(saved_rows or []))


def require_league_access(
    request: Request,
    league_id: str = Depends(resolve_league_path_id),
    user: dict[str, Any] = Depends(require_user),
) -> str:
    """Shared FastAPI dependency for every league-scoped `/v1/leagues/{id}`
    endpoint that does not already resolve "my roster" (which applies the same
    check via `_resolve_my_roster`). Runs before the route body, so a Free
    account asking for a league that is neither one of its saved leagues nor
    its single unsaved-league claim gets the locked payload with no data and
    no compute. Memoised per request. Returns the resolved league id, so it
    is a drop-in for `Depends(resolve_league_path_id)`."""

    memo = getattr(request.state, "league_access", None)
    if memo is None:
        memo = {}
        request.state.league_access = memo
    allowed = memo.get(league_id)
    if allowed is None:
        allowed = _league_access_allowed(user, league_id)
        memo[league_id] = allowed
    if not allowed:
        raise FreeLeagueLocked(league_id)
    return league_id


@app.delete("/v1/leagues/{league_id}/save")
def remove_saved_league(
    league_id: str,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Remove a saved league from the caller's account.

    coridian_, 2026-10-19: "need a way once signed in to add more leauges or
    remove leauges" / "the couldnt load 2 leauges takes up too much space
    and i never selected those leauges to be loaded into the site to
    beguin with" — Portfolio's `saved_leagues` rows aren't only created by
    this service's own `save_league` (an explicit Sleeper import); the
    Streamlit app's automatic context persist (app._persist_supabase_
    account_context, which runs on every league view) also writes/refreshes
    a row for any league the account merely viewed there. Those rows can
    land on an account without ever going through a deliberate "save" step
    on web-next, and if Sleeper can't resolve one at request time it shows
    up in Portfolio's `failed_leagues`. This is the one place a user can
    get rid of a saved league regardless of how it got saved.
    """

    normalized = saved_leagues.normalize_league_id(league_id)
    if not normalized:
        raise HTTPException(status_code=422, detail="league_id is required.")

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    existing, error = account_store.fetch_rows(
        config,
        access_token,
        saved_leagues.LEAGUES_TABLE,
        user_id=user_id,
        extra_query="select=league_id,is_default",
    )
    if error:
        return {"ok": False, "reason": "not_available"}
    removed_row = next((row for row in existing if str(row.get("league_id")) == normalized), None)

    ok, _delete_error = account_store.delete_rows(
        config,
        access_token,
        saved_leagues.LEAGUES_TABLE,
        query=f"user_id=eq.{user_id}&league_id=eq.{normalized}",
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    _forget_saved_leagues_cache(user_id)
    free_tier_ledger.release_league_claims(user_id)

    # The removed league was the account's default — promote the next
    # remaining one so Home/Portfolio still has somewhere to land, instead
    # of silently leaving the account with no default at all.
    if removed_row and removed_row.get("is_default"):
        remaining = [row for row in existing if str(row.get("league_id")) != normalized]
        if remaining:
            account_store.upsert_saved_league(
                config,
                access_token,
                {"user_id": user_id, "league_id": str(remaining[0].get("league_id")), "is_default": True},
            )

    return {"ok": True, "reason": ""}


@app.get("/v1/leagues/{league_id}/warmup-status")
def get_league_warmup_status(
    league_id: str = Depends(resolve_league_path_id),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Which first-load stages of a just-saved league are ready. `state` is
    none (nothing to wait for), running, done or error."""

    return {"ok": True, **league_warmup.read_status(str(user.get("id") or ""), league_id)}


@app.get("/v1/leagues/{league_id}")
def get_league(league_id: str = Depends(resolve_league_path_id), _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    # `default_lens` is the one server-side format decision (redraft ->
    # Non-Dynasty); both clients open on it instead of detecting it themselves.
    return {"ok": True, "league": league, "default_lens": league_value_settings.default_lens_for_league(league)}


@app.get("/v1/leagues/{league_id}/users")
def get_league_users(league_id: str = Depends(require_league_access), _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {"ok": True, "users": sleeper.get_users(league_id)}


@app.get("/v1/leagues/{league_id}/rosters")
def get_league_rosters(league_id: str = Depends(require_league_access), _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {"ok": True, "rosters": sleeper.get_rosters(league_id)}


@app.get("/v1/leagues/{league_id}/team-profiles")
def get_league_team_profiles(league_id: str = Depends(require_league_access), _user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Team identity per roster (name/owner/avatar), keyed by roster_id.

    Reuses modules.sleeper.get_league_roster_profiles verbatim — the same
    team_name/avatar fallback chain (roster metadata -> user metadata ->
    display name -> username) the web app's league workspace uses.
    """

    return {"ok": True, "profiles": sleeper.get_league_roster_profiles(league_id)}


@app.get("/v1/leagues/{league_id}/team-rankings")
def get_league_team_rankings(
    league_id: str = Depends(require_league_access),
    lens: str = "Dynasty",
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Roster Power / Franchise Rank / Draft Capital Rank / standings for every
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

    # Real per-roster injury/balance pass, now accepted as a real compute
    # cost on the dedicated box (see modules.league_rankings.
    # build_roster_health_metrics_frame's docstring — this is the same pass
    # app.py's cached_league_intelligence_frame runs for web). Previously
    # this endpoint ran refine_team_directions directly on the cheap
    # rankings_frame, which has no injury_burden/top_heavy_ratio/
    # impact_tier_starters/elite_tier_count columns at all, so archetype
    # classification silently used modules.team_eval._rank_strength's
    # neutral-default fallback — a real correctness gap against web for a
    # user-facing label (_classify_team_strategy/_assign_team_archetype
    # both gate on these fields, e.g. injury_burden < 4 for "Juggernaut").
    # Cached the same way as the rankings frame itself (30s live-time-bucket
    # Redis single-flight), so this doesn't add per-request latency beyond
    # the first caller in each window.
    health_metrics = league_rankings.build_roster_health_metrics_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if not health_metrics.empty:
        health_cols = [
            "roster_id",
            "injury_burden",
            "injured_starters",
            "health_flag",
            "top_heavy_ratio",
            "impact_tier_starters",
            "elite_tier_count",
        ]
        health_metrics = health_metrics[[c for c in health_cols if c in health_metrics.columns]].copy()
        health_metrics["roster_id"] = pd.to_numeric(health_metrics["roster_id"], errors="coerce")
        rankings_frame = rankings_frame.drop(
            columns=[c for c in health_cols if c != "roster_id" and c in rankings_frame.columns]
        )
        rankings_frame["__roster_id_key__"] = pd.to_numeric(rankings_frame["roster_id"], errors="coerce")
        rankings_frame = rankings_frame.merge(
            health_metrics.rename(columns={"roster_id": "__roster_id_key__"}),
            on="__roster_id_key__",
            how="left",
        ).drop(columns=["__roster_id_key__"])

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

    # Real per-manager activity count off actual Sleeper transaction history
    # (modules.manager_activity) — how many completed moves (trades, waiver
    # claims, free-agent adds/drops) each roster has made this season so
    # far. Same best-effort contract as trade_tendencies above: a scan
    # failure just leaves every team at 0 rather than failing the endpoint.
    try:
        activity_counts = manager_activity.manager_activity_counts_cached(league_id)
    except Exception:
        activity_counts = {}

    # Real per-roster future-pick flow (modules.pick_flow) — acquired vs.
    # sent, 1st-rounders tracked separately — the data half of the
    # "Pick Hoarder"/"Pick Seller" team badge. Same best-effort contract as
    # trade_tendencies/activity_counts above.
    try:
        pick_flow_counts = pick_flow.league_pick_flow_counts_cached(league_id)
    except Exception:
        pick_flow_counts = {}

    # Real per-roster current win/loss streak (modules.team_streaks) — the
    # data half of the "Hot Streak"/"Cold Streak" team badge. Same
    # best-effort contract: a scan failure just leaves every team at a
    # neutral (0) streak rather than failing team-rankings entirely.
    try:
        current_streaks = team_streaks.league_current_streaks_cached(league_id)
    except Exception:
        current_streaks = {}

    # League-wide inputs the per-team badge thresholds below are judged
    # against — each badge is relative to this league's own distribution,
    # not a fixed absolute cutoff (same quartile-by-league-size idiom
    # app.py's `_classify_manager_tendencies`/`_archetype_cutoffs` already
    # use for the equivalent web-side classifications).
    league_size = max(len(rankings_frame), 1)
    top_rank_cut = max(2, int(round(league_size * 0.33)))
    bottom_rank_cut = max(top_rank_cut + 1, int(round(league_size * 0.67)))

    def _activity_count_for(raw_roster_id: Any) -> int:
        try:
            return int(activity_counts.get(int(raw_roster_id), 0))
        except (TypeError, ValueError):
            return 0

    tx_low, tx_high = manager_activity.activity_quartiles(
        _activity_count_for(raw_roster_id) for raw_roster_id in rankings_frame["roster_id"]
    )

    # "Top-Heavy Roster" (stretch badge): starter_score/bench_score are
    # already computed per roster (modules.team_eval's current-value
    # starter/bench split feeding power_rank/starter_rank/bench_rank above)
    # — no new pipeline needed. There's no pre-existing badge threshold for
    # this exact ratio (app.py's own top_heavy_ratio is a *different*, raw
    # unweighted starter/bench split used only as an archetype risk
    # footnote, not comparable 1:1 to this weighted/limited bench_score), so
    # this is judged against this league's own top quartile — a team only
    # earns the badge if its current-value concentration in the starting
    # lineup is more extreme than 75% of the league, a deliberate,
    # documented judgment call per the audit's instructions.
    _zero_series = pd.Series(0, index=rankings_frame.index)
    top_heavy_ratios = (
        pd.to_numeric(rankings_frame.get("starter_score", _zero_series), errors="coerce").fillna(0)
        / pd.to_numeric(rankings_frame.get("bench_score", _zero_series), errors="coerce").fillna(0).clip(lower=1.0)
    )
    if len(top_heavy_ratios) > 1:
        top_heavy_cutoff = float(top_heavy_ratios.quantile(0.75))
    elif len(top_heavy_ratios) == 1:
        top_heavy_cutoff = float(top_heavy_ratios.iloc[0]) + 1.0
    else:
        top_heavy_cutoff = None

    teams: list[dict[str, Any]] = []
    for idx, row in rankings_frame.iterrows():
        roster_id = str(row.get("roster_id"))
        standing = standings_by_roster.get(roster_id, {})
        try:
            roster_id_int: int | None = int(roster_id)
        except (TypeError, ValueError):
            roster_id_int = None
        try:
            tendency = trade_tendencies.get(int(roster_id), {})
        except (TypeError, ValueError):
            tendency = {}
        try:
            activity_count = int(activity_counts.get(int(roster_id), 0))
        except (TypeError, ValueError):
            activity_count = 0

        pick_flow_entry = pick_flow_counts.get(roster_id_int, {}) if roster_id_int is not None else {}
        firsts_acquired = int(pick_flow_entry.get("firsts_acquired") or 0)
        firsts_sent = int(pick_flow_entry.get("firsts_sent") or 0)

        streak_entry = current_streaks.get(roster_id_int, {}) if roster_id_int is not None else {}
        current_streak = int(streak_entry.get("current_streak") or 0)

        age_rank = row.get("age_rank")
        draft_rank = row.get("draft_capital_rank")
        try:
            age_rank_int: int | None = int(age_rank) if age_rank is not None and not pd.isna(age_rank) else None
        except (TypeError, ValueError):
            age_rank_int = None
        try:
            draft_rank_int: int | None = int(draft_rank) if draft_rank is not None and not pd.isna(draft_rank) else None
        except (TypeError, ValueError):
            draft_rank_int = None

        team_badges: list[str] = []
        activity_badge = manager_activity.classify_activity_level(
            transaction_count=activity_count, tx_high=tx_high, tx_low=tx_low
        )
        # ESPN leagues have no transaction feed here (modules.espn_leagues),
        # so a zero count means "unknown", not a "Quiet Manager".
        if activity_badge and not external_leagues.is_external_league_key(league_id):
            team_badges.append(activity_badge)
        pick_flow_badge = pick_flow.classify_pick_flow(firsts_acquired, firsts_sent)
        if pick_flow_badge:
            team_badges.append(pick_flow_badge)
        if age_rank_int is not None and draft_rank_int is not None:
            if age_rank_int >= bottom_rank_cut and draft_rank_int >= bottom_rank_cut:
                team_badges.append("Veteran Collector")
            elif age_rank_int <= top_rank_cut and draft_rank_int <= top_rank_cut:
                team_badges.append("Youth Builder")
        streak_badge = team_streaks.classify_streak_badge(current_streak)
        if streak_badge:
            team_badges.append(streak_badge)
        if top_heavy_cutoff is not None and top_heavy_ratios.loc[idx] >= top_heavy_cutoff:
            team_badges.append("Top-Heavy Roster")

        teams.append(
            {
                "roster_id": roster_id,
                "trade_tendency": tendency.get("tendency", team_trade_history.NEUTRAL),
                "trade_tendency_sell_count": int(tendency.get("sell_count") or 0),
                "trade_tendency_buy_count": int(tendency.get("buy_count") or 0),
                "transaction_activity_count": activity_count,
                "firsts_acquired": firsts_acquired,
                "firsts_sent": firsts_sent,
                "current_streak": current_streak,
                "team_badges": team_badges,
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
                # Already-computed presentation fields off the same
                # standings row League Rankings' web Standings board reads
                # (modules.league_standings.build_league_standings_bundle) —
                # exposed as-is so a client never has to re-derive a
                # win-percentage/playoff-seed label itself.
                "standing_rank": _clean_json_value(standing.get("standing_rank")),
                "win_pct_label": _clean_json_value(standing.get("win_pct_label")),
                "points_for_label": _clean_json_value(standing.get("points_for_label")),
                "points_against_label": _clean_json_value(standing.get("points_against_label")),
                "playoff_status": _clean_json_value(standing.get("playoff_status")),
                "on_playoff_line": bool(standing.get("on_playoff_line")),
                "power_rank": _clean_json_value(row.get("power_rank")),
                "power_rank_tied": bool(row.get("power_rank_tied")),
                # Raw scores backing each rank above — League Rankings' web
                # boards (Roster Power/Franchise/Draft Capital/Starter/Bench)
                # show the real score next to the rank, same as the
                # Streamlit page's render_power_rankings_board. All already
                # computed in modules.league_rankings.build_league_rankings_frame.
                "power_score": _clean_json_value(row.get("power_score")),
                "franchise_rank": _clean_json_value(row.get("franchise_rank")),
                "franchise_rank_tied": bool(row.get("franchise_rank_tied")),
                "franchise_score": _clean_json_value(row.get("franchise_score")),
                "draft_capital_rank": _clean_json_value(row.get("draft_capital_rank")),
                "draft_capital_rank_tied": bool(row.get("draft_capital_rank_tied")),
                "draft_capital_score": _clean_json_value(row.get("draft_capital")),
                "pick_count": _clean_json_value(row.get("pick_count")),
                "first_rounders": _clean_json_value(row.get("first_rounders")),
                "starter_rank": _clean_json_value(row.get("starter_rank")),
                "starter_rank_tied": bool(row.get("starter_rank_tied")),
                "starter_score": _clean_json_value(row.get("starter_score")),
                "bench_rank": _clean_json_value(row.get("bench_rank")),
                "bench_rank_tied": bool(row.get("bench_rank_tied")),
                "bench_score": _clean_json_value(row.get("bench_score")),
                "age_rank": _clean_json_value(row.get("age_rank")),
                "age_rank_tied": bool(row.get("age_rank_tied")),
                "average_age": _clean_json_value(row.get("avg_age")),
                "strategy": _clean_json_value(row.get("strategy")),
                "strategy_label": _clean_json_value(row.get("strategy_label")),
                "archetype": _clean_json_value(row.get("archetype")),
                "archetype_label": _clean_json_value(row.get("archetype_label")),
                "archetype_explanation": _clean_json_value(row.get("archetype_explanation")),
                "archetype_strengths": _as_string_list(row.get("archetype_strengths")),
                "archetype_risks": _as_string_list(row.get("archetype_risks")),
                "archetype_recommendations": _as_string_list(row.get("archetype_recommendations")),
                "injured_starters": _clean_json_value(row.get("injured_starters")),
                "health_flag": _clean_json_value(row.get("health_flag")),
            }
        )

    return {
        "ok": True,
        "teams": teams,
        "reason": "",
        # Standings-board framing (modules.league_standings.
        # build_league_standings_bundle) — exposed so League Rankings' web
        # Standings section can show the same "{season} Standings"/
        # "Through Week N" header and not-ready copy the Streamlit page
        # shows, without recomputing any of it client-side.
        "standings_available": bool(standings_bundle.get("available")),
        "standings_message": _clean_json_value(standings_bundle.get("message")) or "",
        "season": _clean_json_value(standings_bundle.get("season")) or "",
        "week_label": _clean_json_value(standings_bundle.get("week_label")) or "",
        "playoff_teams": _clean_json_value(standings_bundle.get("playoff_teams")),
    }


@app.get("/v1/leagues/{league_id}/playoff-odds")
@_with_sleeper_as_of
def get_league_playoff_odds(
    league_id: str = Depends(require_league_access),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Rest-of-season Monte Carlo playoff-odds simulation for every team.

    Pro-only (2026-10-23): a Free caller gets reason "premium_required" plus
    an upsell and no teams; the simulation never runs for them.

    Real inputs only — see modules.playoff_simulator's module docstring for
    the full methodology: real remaining matchup schedule (Sleeper), real
    Roster Power team strength, real season-to-date record/points for
    tiebreaking, real playoff_teams/playoff_week_start league settings. The
    win-probability model is a single-parameter logistic function of
    Roster-Power differential, calibrated against this league's own real
    results so far once enough of the season has been played, and a
    documented default shape before that.

    Same public, league-wide auth pattern as /team-rankings. Not-ready
    states return 200 with a `reason` (same contract as the other league
    endpoints) rather than an HTTP error: "offseason" (no real results
    yet), "no_playoff_format" (league has no playoff_teams setting
    configured), "no_rankings_data"/"unavailable" (Roster Power/league data
    isn't computable right now).

    Cached for modules.playoff_simulator.PLAYOFF_ODDS_TTL_SECONDS (3 hours)
    per (league_id, lens) — a multi-thousand-trial simulation is real work
    worth sharing across every request for the same league within that
    window, and this is a rest-of-season outlook that can only meaningfully
    change once new real games are played.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    if not _is_pro_caller(user):
        return {
            "ok": True,
            "reason": "premium_required",
            "teams": [],
            "is_premium": False,
            "upsell": _PLAYOFF_ODDS_UPSELL,
        }

    result = playoff_simulator.build_league_playoff_odds_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    return {**result, "is_premium": True, "upsell": None}


# ---------------------------------------------------------------------------
# Games: Season Simulator (what-if) and league Pick'em. See modules/games.py.
# The simulator reuses modules.playoff_simulator; Pick'em storage is optional
# (docs/supabase_games.sql) and answers `available: false` until applied.
# ---------------------------------------------------------------------------

_GAMES_WHAT_IF_UPSELL = {
    "title": "See how a move changes your season",
    "body": (
        "What-if is a Premium feature: add or drop players and see the change "
        "in your playoff odds, seed and wins before you make the move."
    ),
}


def _games_odds_row(team: dict[str, Any]) -> dict[str, Any]:
    return {
        "playoff_probability": team.get("playoff_probability"),
        "median_final_wins": team.get("median_final_wins"),
        "median_final_losses": team.get("median_final_losses"),
        "median_seed": team.get("median_seed"),
        "title_probability": team.get("title_probability"),
        "clinched": bool(team.get("clinched")),
        "eliminated": bool(team.get("eliminated")),
    }


def _games_check_lens(lens: str) -> None:
    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )


@app.get("/v1/leagues/{league_id}/games/season-sim")
@_with_sleeper_as_of
def get_games_season_sim(
    league_id: str = Depends(require_league_access),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Season Simulator baseline: the caller's own rest-of-season odds from the
    shared playoff-odds simulation plus the roster the what-if can drop from.
    Free for everyone; the what-if (POST) is Premium."""

    _games_check_lens(lens)
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)
    base = {"ok": True, "is_premium": is_premium, "upsell": None if is_premium else _GAMES_WHAT_IF_UPSELL}

    odds = playoff_simulator.build_league_playoff_odds_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if odds.get("reason"):
        return {**base, "reason": odds["reason"], "teams": [], "my_team": None, "roster": []}
    my_roster, roster_reason = _resolve_my_roster(user, league_id, profile=profile)
    if not my_roster:
        return {**base, "reason": roster_reason or "no_roster", "teams": [], "my_team": None, "roster": []}

    my_rid = str(my_roster.get("roster_id"))
    teams = [
        {
            "roster_id": t["roster_id"],
            "team_name": t["team_name"],
            "avatar_url": t.get("avatar_url"),
            "record_label": t.get("record_label"),
            "playoff_probability": t["playoff_probability"],
            "title_probability": t.get("title_probability"),
            "median_seed": t["median_seed"],
            "mine": t["roster_id"] == my_rid,
        }
        for t in odds.get("teams") or []
    ]
    my_team = next((t for t in odds.get("teams") or [] if t["roster_id"] == my_rid), None)

    players_df = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    roster: list[dict[str, Any]] = []
    my_ids = {str(pid) for pid in (my_roster.get("players") or []) if pid is not None}
    if my_ids and not players_df.empty and "player_id" in players_df.columns:
        score_field = league_value_settings.valuation_score_field(lens)
        mine_df = players_df[players_df["player_id"].astype(str).isin(my_ids)]
        if score_field in mine_df.columns:
            mine_df = mine_df.sort_values(score_field, ascending=False)
        for _, row in mine_df.iterrows():
            roster.append(
                {
                    "player_id": str(row.get("player_id")),
                    "name": _clean_json_value(row.get("name")),
                    "position": _clean_json_value(row.get("position")),
                    "team": _clean_json_value(row.get("team")),
                    "injury_status": _clean_json_value(row.get("injury_status")),
                    "tier": _clean_json_value(row.get("tier")),
                }
            )

    return {
        **base,
        "reason": "",
        "my_roster_id": my_rid,
        "my_team": _games_odds_row(my_team) if my_team else None,
        "teams": teams,
        "roster": roster,
        "playoff_teams": odds.get("playoff_teams"),
        # Older cached runs predate title odds: report them unavailable, not 0.
        "title_odds": odds.get("title_odds") or {"available": False, "reason": "unavailable"},
        "current_week": odds.get("current_week"),
        "weeks_remaining": odds.get("weeks_remaining"),
        "trials": odds.get("trials"),
        "slope_fitted": odds.get("slope_fitted"),
        "games_used_for_fit": odds.get("games_used_for_fit"),
    }


class GamesWhatIfRequest(BaseModel):
    add: list[str] = Field(default_factory=list, max_length=games.WHAT_IF_MAX_PLAYERS)
    drop: list[str] = Field(default_factory=list, max_length=games.WHAT_IF_MAX_PLAYERS)


@app.post("/v1/leagues/{league_id}/games/season-sim/what-if")
@_with_sleeper_as_of
def post_games_what_if(
    body: GamesWhatIfRequest,
    league_id: str = Depends(require_league_access),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Premium. Re-runs the shared playoff simulation with the caller's Roster
    Power recomputed for the add/drop, against an equally seeded baseline."""

    import zlib

    import numpy as np

    _games_check_lens(lens)
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    if not premium.is_at_least(profile.get("entitlement"), premium.PRO):
        return {"ok": True, "reason": "", "is_premium": False, "upsell": _GAMES_WHAT_IF_UPSELL}

    def not_ready(reason: str) -> dict[str, Any]:
        return {"ok": True, "reason": reason, "is_premium": True, "upsell": None}

    my_roster, roster_reason = _resolve_my_roster(user, league_id, profile=profile)
    if not my_roster:
        return not_ready(roster_reason or "no_roster")
    my_rid = str(my_roster.get("roster_id"))
    current_ids = [str(pid) for pid in (my_roster.get("players") or []) if pid is not None]

    players_df = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if players_df.empty or "player_id" not in players_df.columns:
        return not_ready("no_rankings_data")
    known = {str(pid) for pid in players_df["player_id"]}
    problem = games.validate_roster_change(current_ids, body.add, body.drop, known)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    league = sleeper.get_league(league_id)
    if not league:
        return not_ready("unavailable")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)
    score_field = league_value_settings.valuation_score_field(lens)
    before = games.score_roster(players_df, current_ids, score_field, settings)
    after = games.score_roster(
        players_df, games.apply_roster_change(current_ids, body.add, body.drop), score_field, settings
    )

    frame = league_rankings.build_league_rankings_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    my_power = None
    if not frame.empty:
        match = frame[frame["roster_id"].astype(str) == my_rid]
        if not match.empty:
            my_power = float(match.iloc[0].get("power_score") or 0.0)
    if my_power is None:
        return not_ready("no_rankings_data")
    scenario_power = my_power + (after["total_score"] - before["total_score"])

    seed = zlib.crc32(f"{league_id}:{lens}".encode()) & 0xFFFFFFFF
    base_run = playoff_simulator.build_league_playoff_odds(
        league_id, lens=lens, players_db_path=PLAYERS_DB_PATH, rng=np.random.default_rng(seed)
    )
    if base_run.get("reason"):
        return not_ready(base_run["reason"])
    scenario_run = playoff_simulator.build_league_playoff_odds(
        league_id,
        lens=lens,
        players_db_path=PLAYERS_DB_PATH,
        rng=np.random.default_rng(seed),
        power_overrides={my_rid: scenario_power},
    )
    base_team = next((t for t in base_run["teams"] if t["roster_id"] == my_rid), None)
    scenario_team = next((t for t in scenario_run["teams"] if t["roster_id"] == my_rid), None)
    if not base_team or not scenario_team:
        return not_ready("unavailable")

    touched = set(body.add) | set(body.drop)
    names = {
        str(row.get("player_id")): {
            "player_id": str(row.get("player_id")),
            "name": _clean_json_value(row.get("name")),
            "position": _clean_json_value(row.get("position")),
            "team": _clean_json_value(row.get("team")),
        }
        for _, row in players_df[players_df["player_id"].astype(str).isin(touched)].iterrows()
    }
    return {
        "ok": True,
        "reason": "",
        "is_premium": True,
        "upsell": None,
        "baseline": _games_odds_row(base_team),
        "scenario": _games_odds_row(scenario_team),
        "change": games.compare_odds(base_team, scenario_team),
        "added": [names[pid] for pid in body.add if pid in names],
        "dropped": [names[pid] for pid in body.drop if pid in names],
        "factors": games.what_if_factors(
            before,
            after,
            remaining_games=int(base_team.get("remaining_games") or 0),
            weeks_remaining=int(base_run.get("weeks_remaining") or 0),
            slope_fitted=bool(base_run.get("slope_fitted")),
            games_used_for_fit=int(base_run.get("games_used_for_fit") or 0),
        ),
    }


def _pickem_context(league_id: str) -> tuple[dict[str, Any] | None, str, int, dict[str, Any]]:
    """(league, season, current_week, roster profiles); league None if unknown."""

    league = sleeper.get_league(league_id)
    if not league:
        return None, "", 0, {}
    current_week, _end, _max = league_recaps.league_history_window(league)
    return league, str(league.get("season") or ""), int(current_week or 0), sleeper.get_league_roster_profiles(league_id)


def _pickem_winners(league_id: str, weeks: list[int], profiles: dict[str, Any]) -> dict[int, dict[str, str | None]]:
    """matchup_id -> winning roster id for finished weeks (from real scores)."""

    import concurrent.futures

    if not weeks:
        return {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(weeks))) as pool:
        fetched = list(pool.map(lambda w: sleeper.get_matchups(league_id, w) or [], weeks))
    out: dict[int, dict[str, str | None]] = {}
    for week, matchups in zip(weeks, fetched):
        out[week] = {
            m["matchup_id"]: games.matchup_winner(m) for m in games.group_week_matchups(matchups, profiles)
        }
    return out


@app.get("/v1/leagues/{league_id}/games/pickem")
@_with_sleeper_as_of
def get_games_pickem(
    league_id: str = Depends(require_league_access),
    week: int | None = None,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Weekly pick'em inside the caller's own league: the week's matchups, the
    caller's picks, results once a week is final, and a season leaderboard
    among league members who played. available=false until the tables exist."""

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    token = str(user.get("_access_token") or "")
    league, season, current_week, profiles = _pickem_context(league_id)
    if not league:
        return {"ok": True, "available": False, "reason": "unavailable"}
    if current_week <= 0 or not season:
        return {"ok": True, "available": True, "reason": "offseason"}
    my_roster, roster_reason = _resolve_my_roster(user, league_id)
    if not my_roster:
        return {"ok": True, "available": True, "reason": roster_reason or "no_roster"}
    if not auth_supabase.is_configured(config) or not user_id:
        return {"ok": True, "available": False, "reason": ""}

    try:
        my_rows = games.fetch_my_picks(config, token, user_id, league_id, season)
        try:
            league_rows = games.fetch_league_picks(league_id, season)
        except games.Unavailable:
            league_rows = None
    except games.Unavailable:
        return {"ok": True, "available": False, "reason": ""}

    selected = max(1, min(int(week or current_week), current_week))
    grouped = games.group_week_matchups(sleeper.get_matchups(league_id, selected), profiles)
    my_week_picks = {
        str(r.get("matchup_id")): str(r.get("picked_roster_id"))
        for r in my_rows
        if str(r.get("week")) == str(selected)
    }
    view = games.build_week_view(selected, current_week, grouped, my_week_picks)

    rows = league_rows if league_rows is not None else [{**r, "user_id": user_id} for r in my_rows]
    final_weeks = sorted(
        {int(r["week"]) for r in rows if str(r.get("week", "")).isdigit() and int(r["week"]) < current_week}
    )
    winners = _pickem_winners(league_id, final_weeks, profiles)
    board = games.build_leaderboard(rows, winners, profiles, user_id)
    mine = next((row for row in board if row["mine"]), None)
    return {
        "ok": True,
        "available": True,
        "reason": "",
        "season": season,
        "current_week": current_week,
        "weeks": list(range(1, current_week + 1)),
        "my_roster_id": str(my_roster.get("roster_id")),
        **view,
        "season_record": {"correct": mine["correct"], "graded": mine["graded"]} if mine else {"correct": 0, "graded": 0},
        "leaderboard": board,
        "leaderboard_scope": "league" if league_rows is not None else "you",
    }


class GamesPickRequest(BaseModel):
    week: int = Field(ge=1, le=30)
    matchup_id: str = Field(min_length=1, max_length=16)
    roster_id: str = Field(min_length=1, max_length=16)


@app.post("/v1/leagues/{league_id}/games/pickem/pick")
@_with_sleeper_as_of
def post_games_pickem_pick(
    body: GamesPickRequest,
    league_id: str = Depends(require_league_access),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Save or change a pick. Only league members, only the current week, and
    only before the week's first score lands (server-checked, not just hidden
    in the UI)."""

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    league, season, current_week, profiles = _pickem_context(league_id)
    if not league or not user_id or not auth_supabase.is_configured(config):
        return {"ok": False, "available": False, "reason": "not_available"}
    my_roster, roster_reason = _resolve_my_roster(user, league_id)
    if not my_roster:
        return {"ok": False, "available": True, "reason": roster_reason or "no_roster"}
    if body.week != current_week:
        return {"ok": False, "available": True, "reason": "locked"}
    grouped = games.group_week_matchups(sleeper.get_matchups(league_id, body.week), profiles)
    if games.week_phase(body.week, current_week, grouped) != "open":
        return {"ok": False, "available": True, "reason": "locked"}
    problem = games.pick_error(grouped, body.matchup_id, body.roster_id)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    try:
        games.upsert_pick(
            config,
            str(user.get("_access_token") or ""),
            {
                "user_id": user_id,
                "league_id": league_id,
                "season": season,
                "week": body.week,
                "matchup_id": body.matchup_id,
                "picked_roster_id": body.roster_id,
                "picker_roster_id": str(my_roster.get("roster_id")),
            },
        )
    except games.Unavailable:
        return {"ok": False, "available": False, "reason": "not_available"}
    return {"ok": True, "available": True, "reason": ""}


@app.get("/v1/leagues/{league_id}/draft-center")
def get_league_draft_center(
    league_id: str = Depends(require_league_access),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Draft Center Overview: your own draft posture (if your roster can be
    resolved) plus league-wide draft decision signals and partner discovery.

    Shares the web app's real computation chain: modules.league_rankings
    (build_league_summary_and_draft_capital, build_draft_workspace_frame —
    the latter ported verbatim from app.py, confirmed pure pandas with no
    Streamlit dependency) plus modules.draft_center_cards's already-pure
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

    # Pro-only (2026-10-23), checked before any valuation work. The profile
    # is fetched once and reused for roster resolution below.
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    if not premium.is_at_least(profile.get("entitlement"), premium.PRO):
        return {
            "ok": True,
            "reason": "premium_required",
            "posture": None,
            "posture_reason": "",
            "decision_cards": [],
            "partner_cards": [],
            "is_premium": False,
            "upsell": _DRAFT_CENTER_UPSELL,
        }

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

    # Cached (30s live-time bucket, same idiom as
    # build_league_rankings_frame_cached) — this is the same real
    # per-roster Power/Franchise/Draft-Capital pass Team Rankings/Dashboard
    # already share one cache entry for; Draft Center used to redo it from
    # scratch on every request instead of sharing that cache too.
    df_summary, draft_capital_summary = league_rankings.build_league_summary_and_draft_capital_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
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

    decision_cards = draft_center_cards.build_draft_decision_cards(draft_workspace)
    partner_cards = draft_center_cards.build_draft_partner_cards(draft_workspace)

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
            profile_posture = draft_center_cards.draft_posture_profile(team_row, len(draft_workspace))
            posture_reason = ""
            posture = {
                "label": profile_posture["label"],
                "note": profile_posture["note"],
                "tone": profile_posture["tone"],
                "draft_capital_rank": _clean_json_value(team_row.get("draft_capital_rank")),
                "draft_capital_rank_tied": bool(team_row.get("draft_capital_rank_tied")),
                "draft_capital": _clean_json_value(team_row.get("draft_capital")),
                "future_draft_capital_rank": _clean_json_value(team_row.get("future_draft_capital_rank")),
                "future_draft_capital_rank_tied": bool(team_row.get("future_draft_capital_rank_tied")),
                "future_draft_capital": _clean_json_value(team_row.get("future_draft_capital")),
                "strategy_display": _clean_json_value(team_row.get("strategy_display")),
                "power_rank": _clean_json_value(team_row.get("power_rank")),
                "power_rank_tied": bool(team_row.get("power_rank_tied")),
                "franchise_rank": _clean_json_value(team_row.get("franchise_rank")),
                "franchise_rank_tied": bool(team_row.get("franchise_rank_tied")),
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
        "is_premium": True,
        "upsell": None,
    }


@app.get("/v1/leagues/{league_id}/draft-picks")
def get_league_draft_picks(
    league_id: str = Depends(require_league_access),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
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

    if external_leagues.is_external_league_key(league_id):
        # ESPN's API doesn't expose who owns which future picks, so listing
        # every team's own picks would be a guess. Trade Analyzer runs
        # players-only for ESPN leagues instead.
        return {"ok": True, "picks": [], "reason": espn_leagues.ESPN_NOT_AVAILABLE_REASON}

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

    # Cached (30s live-time bucket, same idiom as
    # build_league_rankings_frame_cached) — this endpoint and Draft Center
    # both ask this exact question for the same league within seconds of
    # each other on a typical session (open Draft Center, tap into Pick
    # Detail), and each used to redo the full per-roster valuation pass
    # from scratch instead of sharing one cache entry.
    df_summary, _ = league_rankings.build_league_summary_and_draft_capital_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if df_summary.empty:
        return {"ok": True, "picks": [], "reason": "no_rankings_data"}

    # Real Sleeper draft-completion check — mirrors app.py's own
    # cached_rookie_draft_context/rookie_draft_status_items call sites (e.g.
    # cached_draft_pick_assets), rather than falling back to
    # list_draft_pick_assets' own league-type-only guess. Without this, a
    # completed rookie draft still showed its picks as available/upcoming
    # trade assets in the mobile Draft Center.
    draft_status = dict(
        draft_assistant.rookie_draft_status_items(
            draft_assistant.rookie_draft_context(
                league_id, league_settings_items=tuple(settings.items())
            )
        )
    )
    # Crowdsourced college scouting signal (modules/college_scouting.py),
    # cached ~10min since it's identical for every caller — see
    # get_cached_crowd_class_strength_by_year's own docstring for why this
    # isn't refetched per request. Gated by class_strength_signal_enabled()
    # (default off — see that function's docstring); {} is always the safe
    # "no crowd signal" value, which _rookie_class_strength_multiplier
    # already treats as pure editorial class strength, unchanged.
    crowd_class_strength = (
        college_scouting.get_cached_crowd_class_strength_by_year(
            auth_supabase.get_supabase_config(), str(user.get("_access_token") or "")
        )
        if college_scouting.class_strength_signal_enabled()
        else {}
    )
    picks = trade_ideas.list_draft_pick_assets(
        league_id,
        df_summary,
        league_settings=settings,
        draft_status=draft_status,
        crowd_class_strength_by_year=crowd_class_strength,
    )
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


# coridian_, 2026-10-19: real reported site-wide load-time regression,
# traced to account_store.fetch_saved_leagues (a plain, uncached Supabase
# round trip) having no cache at all, newly called from inside
# _resolve_my_roster as of the per-league-username fix above -- and
# _resolve_my_roster is itself called from ~14 different single-league
# endpoints (Dashboard, My Team, Matchup, Waivers, Trade Hub, Alerts, GM
# Plan, GM Targets, Draft Center, Trade Analyzer, Trade Finder, League
# Rankings, Team Situation, Live Draft state), so every one of those page
# loads paid a fresh ~150-250ms Supabase round trip that didn't exist
# before today. Short TTL on purpose: saved_leagues only changes on a
# deliberate user action (add/remove/relink a league), so a brief
# staleness window is invisible in practice while still collapsing a
# user's whole burst of navigation (Dashboard -> Waivers -> Trade Hub in
# a few seconds) down to effectively one real fetch.
_SAVED_LEAGUES_TTL_SECONDS = 15

# Real production bug, 2026-10-21 (coridian_, live, confirmed against a real
# account): Sleeper mints a brand-new league_id every season a dynasty
# league rolls over (linked backward via previous_league_id); nothing in
# this codebase re-pointed an already-saved league forward once that
# happened, so a saved_leagues row kept resolving to last season's frozen
# league object forever. Downstream, that silently fed (a) a stale,
# prior-season roster view from _resolve_my_roster below, and (b) a Guess
# the Player leaderboard that only matches leaguemates sharing the exact
# same (stale-or-fresh) league_id, since guess_the_player_leaderboard's
# fetch_league_members queries saved_leagues directly by league_id.
#
# A day-long TTL is deliberate: season rollover is a once-a-year event per
# league, so the only cost of a stale cache entry is a day's delay in
# *noticing* a rollover that already happened -- not a wrong answer (an
# unresolved stale id behaves exactly as it did before this fix: still
# wrong, just not re-checked yet). Keyed by league_id alone, not per-user:
# "is this league_id this season's version" is the same fact for every
# saved_leagues row that points at it, so the first user to trigger the
# check resolves it for every leaguemate, not just themselves.
_LEAGUE_ROLLOVER_CACHE_TTL_SECONDS = 24 * 60 * 60
# Bounds _apply_league_rollover_resolution's per-row concurrency (each
# worker makes at most 3 Sleeper GETs on a cache miss); same ceiling as
# Portfolio's own fan-out.
_LEAGUE_ROLLOVER_MAX_WORKERS = 8


def _resolve_league_rollover_cached(league_id: str, sleeper_username: str) -> str:
    """Cached wrapper around sleeper_leagues.resolve_saved_league_rollover.
    Fails open to the original league_id on any cache or lookup problem --
    never raises, never blocks a request on this."""

    if not league_id or not sleeper_username:
        return league_id
    cache_key = redis_cache.build_cache_key("league_rollover", league_id)
    try:
        return redis_cache.redis_single_flight_cache(
            cache_key=cache_key,
            ttl_seconds=_LEAGUE_ROLLOVER_CACHE_TTL_SECONDS,
            compute=lambda: sleeper_leagues.resolve_saved_league_rollover(league_id, sleeper_username),
        )
    except Exception:
        try:
            return sleeper_leagues.resolve_saved_league_rollover(league_id, sleeper_username)
        except Exception:
            return league_id


def _apply_league_rollover_resolution(
    config: dict, access_token: str, user_id: str, rows: list[dict]
) -> list[dict]:
    """Returns `rows` with any stale, rolled-over-away-from league_id
    swapped for its current-season continuation. A resolved row is also
    migrated in Supabase (account_store.migrate_saved_league) -- best
    effort, a failed migration never blocks using the correct id for THIS
    response -- so the next fetch, and any OTHER leaguemate's own
    leaderboard/roster query, see the fixed row too, without each member
    having to independently trigger a resolution.

    Each row's lookup runs concurrently (Portfolio perf audit,
    2026-10-21): a cold `_resolve_league_rollover_cached` miss costs 3
    sequential Sleeper round trips (user, this season's leagues, last
    season's leagues), and this used to pay them row after row -- a
    measured ~1.5s for a real 5-league account, all of it ahead of
    Portfolio's own per-league fan-out. Rows are independent (one Redis
    key per league_id), so they resolve in parallel and the results are
    re-joined in the original row order."""

    dict_rows = [row for row in rows if isinstance(row, dict)]

    def _resolve_row(row: dict) -> str:
        old_league_id = str(row.get("league_id") or "").strip()
        sleeper_username = str(row.get("sleeper_username") or "").strip()
        if not old_league_id or not sleeper_username:
            return ""
        return _resolve_league_rollover_cached(old_league_id, sleeper_username)

    resolvable = [
        row
        for row in dict_rows
        if str(row.get("league_id") or "").strip() and str(row.get("sleeper_username") or "").strip()
    ]
    if len(resolvable) > 1:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(resolvable), _LEAGUE_ROLLOVER_MAX_WORKERS),
            thread_name_prefix="dgm-rollover",
        ) as executor:
            resolved_ids = list(executor.map(_resolve_row, dict_rows))
    else:
        resolved_ids = [_resolve_row(row) for row in dict_rows]

    resolved_rows: list[dict] = []
    for row, resolved_league_id in zip(dict_rows, resolved_ids):
        old_league_id = str(row.get("league_id") or "").strip()
        sleeper_username = str(row.get("sleeper_username") or "").strip()
        if not old_league_id or not sleeper_username:
            resolved_rows.append(row)
            continue
        if not resolved_league_id or resolved_league_id == old_league_id:
            resolved_rows.append(row)
            continue
        try:
            account_store.migrate_saved_league(
                config,
                access_token,
                user_id=user_id,
                old_league_id=old_league_id,
                new_league_id=resolved_league_id,
                sleeper_username=sleeper_username,
                league_name=str(row.get("league_name") or ""),
                owner_id=str(row.get("owner_id") or ""),
                roster_id=row.get("roster_id"),
                team_id=row.get("team_id"),
                is_default=bool(row.get("is_default")),
            )
        except Exception:
            pass
        resolved_row = dict(row)
        resolved_row["league_id"] = resolved_league_id
        resolved_rows.append(resolved_row)
    return resolved_rows


def _forget_saved_leagues_cache(user_id: str) -> None:
    try:
        redis_cache.get_redis_client().delete(redis_cache.build_cache_key("saved_leagues", user_id))
    except Exception:
        pass


def _fetch_saved_leagues_cached(config: dict, access_token: str, user_id: str) -> tuple[list[dict], str]:
    cache_key = redis_cache.build_cache_key("saved_leagues", user_id)
    try:
        rows, error = redis_cache.redis_single_flight_cache(
            cache_key=cache_key,
            ttl_seconds=_SAVED_LEAGUES_TTL_SECONDS,
            compute=lambda: account_store.fetch_saved_leagues(config, access_token, user_id=user_id),
        )
    except Exception:
        # Same fail-open contract redis_single_flight_cache documents for a
        # Redis outage -- never let a cache-layer problem turn into a
        # roster-resolution failure.
        rows, error = account_store.fetch_saved_leagues(config, access_token, user_id=user_id)
    if error or not rows:
        return rows, error
    return _apply_league_rollover_resolution(config, access_token, user_id, rows), error


def _free_league_allowed(
    user_id: str,
    profile: dict[str, Any],
    league_id: str,
    saved_rows: Any,
) -> bool:
    """Free league cap on the READ side. save_league enforces
    MAX_LEAGUES_FREE when saving, but every roster-resolved endpoint
    (Trade Hub, Dashboard, All Trades, ...) used to resolve the caller's
    roster in ANY Sleeper league they belong to, saved or not -- so a Free
    user could simply request other leagues' ids. A Free account may use
    only its saved leagues, plus (while it has fewer saved leagues than
    its cap) leagues claimed in the server-side ledger. Pro/Front Office,
    and an errored profile read (fail-open on a transport hiccup), are
    unaffected."""

    if profile.get("status") == "error":
        return True
    if premium.is_at_least(profile.get("entitlement"), premium.PRO):
        return True
    normalized = saved_leagues.normalize_league_id(league_id)
    rows = [row for row in (saved_rows or []) if isinstance(row, dict)]
    saved_ids = {saved_leagues.normalize_league_id(row.get("league_id")) for row in rows}
    if normalized in saved_ids:
        return True
    capacity = saved_leagues.max_leagues_for_entitlement(profile.get("entitlement")) - len(saved_ids)
    return free_tier_ledger.claim_league(user_id, normalized, capacity)


def _resolve_my_roster(
    user: dict[str, Any],
    league_id: str,
    *,
    profile: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Identify which of this league's rosters belongs to the signed-in user.

    Resolves via a Sleeper username -> Sleeper user_id -> the roster whose
    owner_id matches. All non-matches are expected, everyday states (not
    errors) — callers return 200 with the `reason` rather than an HTTP
    error status for any of them.

    coridian_, real production repro: an account that links a SECOND
    Sleeper username (e.g. a throwaway test league) overwrites
    profiles.sleeper_username — the single, global value this function used
    to read exclusively — which silently broke roster resolution for every
    OTHER already-saved league still linked under the first username, even
    though saved_leagues.sleeper_username (captured per-league, at save
    time) still has the right one sitting right there. Now prefers that
    per-league value when a saved_leagues row exists for this league_id,
    falling back to the profile's global value otherwise (the exact
    previous behavior, unchanged for the common one-Sleeper-username case
    and for leagues not yet saved, e.g. mid-import).

    `profile` lets a caller that already fetched the profile (e.g. for
    entitlement) pass it in instead of this function fetching it again —
    same Supabase round trip, not two.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if external_leagues.is_external_league_key(league_id):
        return _resolve_my_espn_roster(config, access_token, user_id, league_id)
    if profile is None:
        profile = _fetch_profile_fields(config, user_id, access_token) if user_id else {}

    sleeper_username = ""
    saved_rows_for_cap: list[Any] | None = None
    if user_id:
        saved_rows, saved_error = _fetch_saved_leagues_cached(config, access_token, user_id)
        if not saved_error:
            saved_rows_for_cap = list(saved_rows or [])
            normalized_league_id = saved_leagues.normalize_league_id(league_id)
            for row in saved_rows:
                if saved_leagues.normalize_league_id(row.get("league_id")) == normalized_league_id:
                    sleeper_username = str(row.get("sleeper_username") or "")
                    break
    if not sleeper_username:
        sleeper_username = str(profile.get("sleeper_username") or "")
    if not sleeper_username:
        return None, "no_sleeper_username_linked"

    if (
        user_id
        and saved_rows_for_cap is not None
        and not _free_league_allowed(user_id, profile, league_id, saved_rows_for_cap)
    ):
        return None, FREE_LEAGUE_CAP_REASON

    sleeper_user_id = sleeper_leagues.resolve_sleeper_user_id(sleeper_username)
    if not sleeper_user_id:
        return None, "sleeper_user_not_found"

    for roster in sleeper.get_rosters(league_id):
        if str(roster.get("owner_id") or "") == sleeper_user_id:
            return roster, ""

    return None, "not_a_member_of_league"


def _resolve_my_espn_roster(
    config: dict, access_token: str, user_id: str, league_id: str
) -> tuple[dict[str, Any] | None, str]:
    """ESPN has no username to match on (public ESPN leagues only expose
    team names), so the user picks their team at import time and it is
    stored as this league's saved_leagues.roster_id. No saved row (or no
    team on it) is `espn_team_not_selected`; a team that has since left the
    league is `not_a_member_of_league`."""

    roster_id = ""
    if user_id:
        saved_rows, saved_error = _fetch_saved_leagues_cached(config, access_token, user_id)
        if not saved_error:
            for row in saved_rows:
                if saved_leagues.normalize_league_id(row.get("league_id")) == league_id:
                    roster_id = str(row.get("roster_id") or row.get("team_id") or "").strip()
                    break
    if not roster_id:
        return None, "espn_team_not_selected"
    rosters = sleeper.get_rosters(league_id)
    if not rosters:
        return None, "league_not_found"
    for roster in rosters:
        if str(roster.get("roster_id") or "") == roster_id:
            return roster, ""
    return None, "not_a_member_of_league"


@app.get("/v1/leagues/{league_id}/live-draft")
def get_league_live_draft_discovery(
    league_id: str = Depends(require_league_access),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Discover this league's Sleeper drafts so the client can gate the
    read-only live draft assistant the same way modules.live_draft_ui's
    Streamlit route does: only show it while a draft is in progress or
    paused, and offer a selector when more than one draft qualifies.

    Wraps modules.live_draft.discover_live_drafts verbatim (no new
    discovery logic here) — this is the first integration of
    modules/live_draft.py outside Streamlit; it has no mobile reference
    screen (see Live Draft's own revision notes), so this endpoint and its
    sibling below are new, not a port of an existing mobile endpoint.

    `is_premium` rides along here too (coridian_, 2026-10-18: "Live draft
    needs to be locked") even though this endpoint's own drafts list is
    just discovery metadata (status/season/rounds), not the gated
    recommendations/board — so a Free caller still sees whether a live
    draft exists and gets a clear reason to upgrade, instead of a blank
    page with no explanation. The real gate (withheld board/recommendation
    data) is on the sibling state endpoint below.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    discovery = live_draft.discover_live_drafts(
        league_id,
        fetch_league_drafts=sleeper.get_league_drafts,
        fetch_draft=sleeper.get_draft,
    )
    drafts = [
        {
            "draft_id": live_draft.safe_text(draft.get("draft_id")),
            "season": live_draft.safe_text(draft.get("season")),
            "status": live_draft.normalize_draft_status(draft.get("status")),
            "rounds": live_draft.draft_round_count(draft),
            "name": live_draft.safe_text(
                (draft.get("metadata") or {}).get("name")
                if isinstance(draft.get("metadata"), dict)
                else ""
            ),
        }
        for draft in (discovery.get("drafts") or [])
        if live_draft.normalize_draft_status(draft.get("status")) in live_draft.LIVE_DRAFT_SUPPORTED_STATUSES
    ]
    active = discovery.get("active_draft") or {}
    return {
        "ok": True,
        "error": discovery.get("error") or "",
        "drafts": drafts,
        "active_draft_id": live_draft.safe_text(active.get("draft_id")),
        "is_premium": is_premium,
        "upsell": None if is_premium else _LIVE_DRAFT_UPSELL,
    }


def _project_live_draft_pick_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "pick_no": _clean_json_value(row.get("pick_no")),
        "round": _clean_json_value(row.get("round")),
        "round_pick": _clean_json_value(row.get("round_pick")),
        "player_id": _clean_json_value(row.get("player_id")),
        "player_name": _clean_json_value(row.get("player_name")),
        "position": _clean_json_value(row.get("position")),
        "team": _clean_json_value(row.get("team")),
        "fantasy_team": _clean_json_value(row.get("fantasy_team")),
        "is_mine": bool(row.get("is_mine")),
    }


def _project_live_draft_recommendation(
    rec: dict[str, Any], rating_by_player_id: dict[str, Any] | None = None
) -> dict[str, Any]:
    player_id = _clean_json_value(rec.get("player_id"))
    return {
        "player_id": player_id,
        "name": _clean_json_value(rec.get("name")),
        "position": _clean_json_value(rec.get("position")),
        "team": _clean_json_value(rec.get("team")),
        "age": _clean_json_value(rec.get("age")),
        "tier": _clean_json_value(rec.get("tier")),
        "league_adjusted_draft_score": _clean_json_value(rec.get("league_adjusted_draft_score")),
        "overall_rating": _clean_json_value((rating_by_player_id or {}).get(str(player_id or ""))),
        "recommendation_role": _clean_json_value(rec.get("recommendation_role")),
        "recommendation_reason": _clean_json_value(rec.get("recommendation_reason")),
        "position_need_impact": _clean_json_value(rec.get("position_need_impact")),
        "immediate_roster_impact": _clean_json_value(rec.get("immediate_roster_impact")),
        "confidence": _clean_json_value(rec.get("confidence")),
        "adp_delta": _clean_json_value(rec.get("adp_delta")),
    }


def _project_live_draft_ranking_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": _clean_json_value(row.get("player_id")),
        "name": _clean_json_value(row.get("name")),
        "position": _clean_json_value(row.get("position")),
        "team": _clean_json_value(row.get("team")),
        "age": _clean_json_value(row.get("age")),
        "tier": _clean_json_value(row.get("tier")),
        "is_rookie": bool(row.get("is_rookie")),
        "overall_rank": _clean_json_value(row.get("overall_rank")),
        "position_rank": _clean_json_value(row.get("position_rank")),
        "canonical_overall_rank": _clean_json_value(row.get("canonical_overall_rank")),
        "canonical_position_rank": _clean_json_value(row.get("canonical_position_rank")),
        "rank_scoring_format": _clean_json_value(row.get("rank_scoring_format")),
        "rank_unavailable_reason": _clean_json_value(row.get("rank_unavailable_reason")),
        "base_value": _clean_json_value(row.get("base_value")),
        # Same columns modules/live_draft.py already computes onto this same
        # board DataFrame (format_adjustment/scarcity_score/roster_fit_score/
        # age_strategy_adjustment/availability_adjustment sum, with
        # base_value, into league_adjusted_draft_score) — the classic
        # Streamlit page's "Score breakdown" expander already reads these
        # exact columns (modules/live_draft_ui.py); just not previously
        # serialized here, which was the one piece of Live Draft still
        # linking out to that classic page (coridian_: "another redirect to
        # the classic website to view the full live draft").
        "format_adjustment": _clean_json_value(row.get("format_adjustment")),
        "scarcity_score": _clean_json_value(row.get("scarcity_score")),
        "roster_fit_score": _clean_json_value(row.get("roster_fit_score")),
        "age_strategy_adjustment": _clean_json_value(row.get("age_strategy_adjustment")),
        "availability_adjustment": _clean_json_value(row.get("availability_adjustment")),
        "league_adjusted_draft_score": _clean_json_value(row.get("league_adjusted_draft_score")),
        "overall_rating": _clean_json_value(row.get("overall_rating")),
        "movement": _clean_json_value(row.get("movement")),
        "recommendation_label": _clean_json_value(row.get("recommendation_label")),
        "recommendation_reason": _clean_json_value(row.get("recommendation_reason")),
    }


def _project_live_draft_team_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "roster_id": _clean_json_value(row.get("roster_id")),
        "team_name": _clean_json_value(row.get("team_name")),
        "is_mine": bool(row.get("is_mine")),
        "team_rank": _clean_json_value(row.get("team_rank")),
        "movement": _clean_json_value(row.get("movement")),
        "trend_label": _clean_json_value(row.get("trend_label")),
        "live_team_score": _clean_json_value(row.get("live_team_score")),
        "roster_count": _clean_json_value(row.get("roster_count")),
        "pick_count": _clean_json_value(row.get("pick_count")),
        "positions": _clean_json_value(row.get("positions")),
        "top_player": _clean_json_value(row.get("top_player")),
        "starter_value": _clean_json_value(row.get("starter_value")),
        "total_value": _clean_json_value(row.get("total_value")),
    }


LIVE_DRAFT_MAX_RANKING_ROWS = 150
LIVE_DRAFT_MAX_PICK_ROWS = 60


@app.get("/v1/leagues/{league_id}/live-draft/{draft_id}")
def get_league_live_draft_state(
    draft_id: str,
    league_id: str = Depends(require_league_access),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Polled read-only live draft board snapshot: on-the-clock status, the
    Best Available / Best Fit / Safe / Upside / Position Need recommendation
    briefings, the full available-player board reranked live for this
    league and roster, a live roster-strength team board, and recent pick
    history.

    Wraps modules.live_draft.build_live_draft_state verbatim — the exact
    engine modules/live_draft_ui.py's Streamlit route already polls every
    LIVE_DRAFT_POLL_INTERVAL_SECONDS, so this is a thin transport layer,
    never a second scoring/ranking implementation.

    No server-side rank-movement tracking: Streamlit keeps the previous
    poll's ranks in st.session_state and diffs them into `movement`; this
    endpoint has no session, so it always returns `movement=0` and the
    client instead diffs two consecutive polls' overall_rank itself (see
    web-next's lib/liveDraftPresentation.ts) — trivial arithmetic over
    numbers this endpoint already computed, not a re-derivation of the
    valuation itself. Keeps this endpoint stateless like every sibling
    endpoint in this file.

    The hypothetical mid-draft Trade Evaluator now has its own pair of
    endpoints (GET/POST .../trade-evaluator below) rather than living here —
    it needs a different request shape (a submitted send/receive package,
    not a poll) and its own fresh picks/rosters read right before scoring
    (so a pick made between page-load and submit is caught). The detailed
    per-field score breakdown table is still NOT covered by any endpoint —
    that stays on the classic Streamlit page for now (deep-linked from the
    Next.js page), same "not every pane has a thin-wrapper endpoint yet"
    scope Draft Center's own docstring already notes for Current
    Draft/History and Scouting.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    draft = sleeper.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    status = live_draft.normalize_draft_status(draft.get("status"))
    if status not in live_draft.LIVE_DRAFT_SUPPORTED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="This draft isn't in a status the live draft assistant supports.",
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    # coridian_, 2026-10-18: "Live draft needs to be locked." Checked here —
    # after the 404/409 checks above (a bogus league/draft or an
    # unsupported status is a real error regardless of tier, same as every
    # other endpoint in this file) but before any of the real valuation
    # work below, so a Free caller never pays for the live-draft poll's
    # real cost just to be told to upgrade.
    if not premium.is_at_least(profile.get("entitlement"), premium.PRO):
        return {"ok": True, "reason": "", "state": None, "is_premium": False, "upsell": _LIVE_DRAFT_UPSELL}

    settings = league_value_settings.detect_league_value_settings_from_payload(league)
    score_field = league_value_settings.valuation_score_field(lens)

    # Same (league_id, lens)-scoped cached valuation pass /rankings and
    # /draft-picks already share — never a second players.db load/value
    # pass for this endpoint.
    players_df = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if players_df.empty:
        return {"ok": True, "reason": "no_player_data", "state": None, "is_premium": True, "upsell": None}

    picks, pick_error = live_draft.fetch_sleeper_draft_picks(draft_id)
    rosters = sleeper.get_rosters(league_id)
    roster_profiles = sleeper.get_league_roster_profiles(league_id)
    # Reuses the profile already fetched for the premium gate above instead
    # of a second identical Supabase round trip — same contract
    # _resolve_my_roster's own `profile` param already documents.
    my_roster, _roster_reason = _resolve_my_roster(user, league_id, profile=profile)
    my_roster_id = my_roster.get("roster_id") if my_roster else None
    my_roster_player_ids = {
        str(player_id) for player_id in ((my_roster or {}).get("players") or []) if player_id is not None
    }
    roster_df = (
        players_df[players_df["player_id"].astype(str).isin(my_roster_player_ids)].copy()
        if my_roster_player_ids and "player_id" in players_df.columns
        else players_df.iloc[0:0].copy()
    )

    state = live_draft.build_live_draft_state(
        draft=draft,
        picks=picks,
        df_players=players_df,
        roster_df=roster_df,
        roster_profiles=roster_profiles,
        rosters=rosters,
        my_roster_id=my_roster_id,
        league_settings=settings,
        score_field=score_field,
    )

    rankings_df = state.get("rankings")
    team_rankings_df = state.get("team_rankings")
    pick_rows = state.get("pick_rows") or []

    # 0-99 "OVR" badge — same player_quick_view.overall_ratings_for_pool
    # /rankings already uses, computed over this board's full available
    # pool (same "before any limit truncation" contract that endpoint's own
    # comment documents) so Best Available / recommendations / the ranking
    # list all show the one consistent OVR, never a second gauge formula
    # invented for this page. Looked up by player_id for recommendations
    # (already-materialized dicts from a rankings snapshot taken before this
    # column existed) rather than recomputed a second time.
    rating_by_player_id: dict[str, Any] = {}
    if rankings_df is not None and not rankings_df.empty and score_field in rankings_df.columns:
        rankings_df = rankings_df.copy()
        rankings_df["overall_rating"] = player_quick_view.overall_ratings_for_pool(
            rankings_df, score_column=score_field
        )
        rating_by_player_id = {
            str(row.get("player_id")): row.get("overall_rating")
            for row in rankings_df.to_dict("records")
            if row.get("player_id")
        }

    return {
        "ok": True,
        "reason": "",
        "is_premium": True,
        "upsell": None,
        "pick_data_stale": bool(pick_error),
        "status": state.get("status"),
        "rounds": _clean_json_value(state.get("rounds")),
        "teams": _clean_json_value(state.get("teams")),
        "picks_made": _clean_json_value(state.get("picks_made")),
        "current_pick": _clean_json_value(state.get("current_pick")),
        "current_round": _clean_json_value(state.get("current_round")),
        "current_team_name": state.get("current_team_name"),
        "current_manager_name": state.get("current_manager_name"),
        "my_slot": _clean_json_value(state.get("my_slot")),
        "is_my_pick": bool(state.get("is_my_pick")),
        "picks_until_mine": _clean_json_value(state.get("picks_until_mine")),
        "my_upcoming_picks": [_clean_json_value(pick) for pick in (state.get("my_upcoming_picks") or [])],
        "positional_run": state.get("positional_run"),
        "last_updated": state.get("last_updated"),
        "score_label": league_display.league_score_label(score_field),
        "league_settings": {
            "qb_format": settings.get("qb_format"),
            "scoring_format": settings.get("scoring_format"),
            "league_format": settings.get("league_format"),
        },
        "recommendations": [
            _project_live_draft_recommendation(rec, rating_by_player_id)
            for rec in (state.get("recommendations") or [])
        ],
        "pick_rows": [_project_live_draft_pick_row(row) for row in pick_rows[-LIVE_DRAFT_MAX_PICK_ROWS:]],
        "rankings": (
            [
                _project_live_draft_ranking_row(row)
                for row in rankings_df.head(LIVE_DRAFT_MAX_RANKING_ROWS).to_dict("records")
            ]
            if rankings_df is not None and not rankings_df.empty
            else []
        ),
        "team_rankings": (
            [_project_live_draft_team_row(row) for row in team_rankings_df.to_dict("records")]
            if team_rankings_df is not None and not team_rankings_df.empty
            else []
        ),
    }


def _load_active_live_draft(league_id: str, draft_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Shared league/draft lookup + status gate for the Trade Evaluator's
    two endpoints below. Gates on LIVE_DRAFT_ACTIVE_STATUSES ("drafting" /
    "paused"), the same narrower set modules/live_draft_ui.py's
    `_render_trade_evaluator` call site checks (line ~1087: it renders the
    form only while the draft is actually in progress, unlike the main
    board endpoint above which also serves "pre_draft"/"complete")."""

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    draft = sleeper.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    status = live_draft.normalize_draft_status(draft.get("status"))
    if status not in live_draft.LIVE_DRAFT_ACTIVE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="The Trade Evaluator is only available while this draft is in progress or paused.",
        )
    return league, draft


@app.get("/v1/leagues/{league_id}/live-draft/{draft_id}/trade-evaluator")
def get_live_draft_trade_evaluator_options(
    draft_id: str,
    league_id: str = Depends(require_league_access),
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """The one piece of data the hypothetical mid-draft Trade Evaluator
    needs that the client doesn't already have: every pick slot in this
    draft room that has NOT been made yet, labeled for a picker.

    Already-drafted players (the other side of the trade) are NOT
    refetched here — the client already holds them in `pick_rows` from
    GET .../live-draft/{draft_id} (player_id/player_name/position/
    fantasy_team), so reusing that avoids a second identical read.

    Wraps modules.live_draft_trade_evaluator.remaining_pick_options
    verbatim — no new pick-slot logic here, see that module's own
    docstring for the full reuse chain back to modules.trade_ideas.
    """

    _league, draft = _load_active_live_draft(league_id, draft_id)
    # Live Draft is Pro-only (GET .../live-draft/{id} withholds its state);
    # the evaluator sub-routes were reachable by Free callers directly.
    if not _manager_tendencies_gate(_user):
        return {
            "ok": True, "reason": "", "pick_data_stale": False, "pick_options": [],
            "is_premium": False, "upsell": _LIVE_DRAFT_UPSELL,
        }
    picks, pick_error = live_draft.fetch_sleeper_draft_picks(draft_id)
    rosters = sleeper.get_rosters(league_id)
    roster_profiles = sleeper.get_league_roster_profiles(league_id)
    rounds = live_draft.draft_round_count(draft)
    teams = live_draft.draft_team_count(draft, rosters)

    pick_options = live_draft_trade_evaluator.remaining_pick_options(
        draft=draft,
        rosters=rosters,
        picks=picks,
        rounds=rounds,
        teams=teams,
        roster_profiles=roster_profiles,
    )
    return {
        "ok": True,
        "reason": "",
        "pick_data_stale": bool(pick_error),
        "pick_options": [
            {"pick_key": option.get("pick_key"), "label": option.get("label")}
            for option in pick_options
        ],
    }


class LiveDraftTradeEvaluatorRequest(BaseModel):
    send_pick_keys: list[str] = Field(default_factory=list)
    receive_pick_keys: list[str] = Field(default_factory=list)
    send_player_ids: list[str] = Field(default_factory=list)
    receive_player_ids: list[str] = Field(default_factory=list)
    lens: str = "Dynasty"


def _project_live_draft_trade_asset(asset: dict[str, Any]) -> dict[str, Any]:
    """Project a modules.live_draft_trade_evaluator asset dict onto the same
    wire shape as the app's existing `TradeAsset` type (lib/api.ts) so the
    client reuses TradeAssetRow/ExchangeSide verbatim instead of needing a
    second adapter."""

    is_pick = asset.get("asset_type") == "pick"
    return {
        "asset_type": asset.get("asset_type"),
        "player_id": _clean_json_value(asset.get("player_id")) if not is_pick else None,
        "name": _clean_json_value(asset.get("name")),
        "label": _clean_json_value(asset.get("label")),
        "position": _clean_json_value(asset.get("position")),
        "team": _clean_json_value(asset.get("team")),
        "age": _clean_json_value(asset.get("age")),
        "score": _clean_json_value(asset.get("score")),
        "injury_status": _clean_json_value(asset.get("injury_status")) if not is_pick else None,
        "tier": _clean_json_value(asset.get("player_tier")) if not is_pick else None,
        "season": str(asset.get("season")) if is_pick and asset.get("season") else None,
        "round": str(asset.get("round")) if is_pick and asset.get("round") else None,
        "owner_team_name": _clean_json_value(asset.get("owner_team_name")) if is_pick else None,
    }


@app.post("/v1/leagues/{league_id}/live-draft/{draft_id}/trade-evaluator")
def post_live_draft_trade_evaluator(
    draft_id: str,
    body: LiveDraftTradeEvaluatorRequest,
    league_id: str = Depends(require_league_access),
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Hypothetical mid-draft trade evaluator: totals + a Favorable / Fair /
    Slight Overpay / Major Overpay verdict for a proposed send/receive
    package of not-yet-made picks and already-drafted players.

    Wraps modules.live_draft_trade_evaluator.evaluate_trade verbatim (via
    pick_asset_for_option/drafted_player_asset for the two asset sides) —
    the exact same engine modules/live_draft_ui.py's Streamlit form already
    calls. No valuation logic is reimplemented here: pick values come from
    modules.trade_ideas.list_draft_pick_assets (the same per-pick pricing
    Trade Analyzer/Draft Center use) with modules.league_rankings.
    safe_pick_value's static round chart as fallback, and player values
    come straight from the same league-valued players frame every other
    lens-aware endpoint in this file shares.

    Re-reads picks/rosters fresh on every call (never trusts a client-held
    snapshot) and re-validates every selected pick slot is still open right
    before scoring — the same "re-check against the freshest polled picks"
    discipline `_render_trade_evaluator`'s own comment documents, since a
    pick can be made by another team between when this page loaded and when
    the user submits. A stale pick returns `reason: "stale_picks"` with the
    offending keys rather than an HTTP error, so the client can ask the user
    to refresh their selection and resubmit — an everyday state, not a
    failure.
    """

    if body.lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )
    if not (body.send_pick_keys or body.send_player_ids):
        raise HTTPException(status_code=422, detail="Add at least one pick or player to the side you send.")
    if not (body.receive_pick_keys or body.receive_player_ids):
        raise HTTPException(status_code=422, detail="Add at least one pick or player to the side you receive.")
    overlap_picks = set(body.send_pick_keys) & set(body.receive_pick_keys)
    overlap_players = set(body.send_player_ids) & set(body.receive_player_ids)
    if overlap_picks or overlap_players:
        raise HTTPException(status_code=422, detail="The same pick or player can't be on both sides of a trade.")

    league, draft = _load_active_live_draft(league_id, draft_id)
    if not _manager_tendencies_gate(_user):
        return {
            "ok": True, "reason": "premium_required", "stale_pick_keys": [], "verdict": None,
            "is_premium": False, "upsell": _LIVE_DRAFT_UPSELL,
        }
    picks, _pick_error = live_draft.fetch_sleeper_draft_picks(draft_id)
    rosters = sleeper.get_rosters(league_id)
    roster_profiles = sleeper.get_league_roster_profiles(league_id)
    rounds = live_draft.draft_round_count(draft)
    teams = live_draft.draft_team_count(draft, rosters)
    season = live_draft.safe_int(draft.get("season"), 0)

    pick_options = live_draft_trade_evaluator.remaining_pick_options(
        draft=draft,
        rosters=rosters,
        picks=picks,
        rounds=rounds,
        teams=teams,
        roster_profiles=roster_profiles,
    )
    selected_pick_keys = list(dict.fromkeys(body.send_pick_keys + body.receive_pick_keys))
    stale_keys = live_draft_trade_evaluator.validate_pick_keys_still_open(
        selected_pick_keys, open_options=pick_options
    )
    if stale_keys:
        return {"ok": True, "reason": "stale_picks", "stale_pick_keys": stale_keys}

    option_by_key = {option.get("pick_key"): option for option in pick_options}
    settings = league_value_settings.detect_league_value_settings_from_payload(league)
    score_field = league_value_settings.valuation_score_field(body.lens)

    players_df = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=body.lens, players_db_path=PLAYERS_DB_PATH
    )

    # Same (league_id, lens)-scoped cache /draft-picks and /trade-analyzer
    # already share — only computed at all when a pick is actually on
    # either side of this proposed package.
    draft_pick_assets: list[dict[str, Any]] = []
    if body.send_pick_keys or body.receive_pick_keys:
        pick_summary, _ = league_rankings.build_league_summary_and_draft_capital_cached(
            league_id=league_id, lens=body.lens, players_db_path=PLAYERS_DB_PATH
        )
        if not pick_summary.empty:
            draft_pick_assets = trade_ideas.list_draft_pick_assets(
                league_id, pick_summary, league_settings=settings
            )

    def build_assets(pick_keys: list[str], player_ids: list[str]) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        for key in pick_keys:
            option = option_by_key.get(key)
            if option is None:
                continue
            assets.append(
                live_draft_trade_evaluator.pick_asset_for_option(
                    option, season=season, draft_pick_assets=draft_pick_assets
                )
            )
        if player_ids and players_df is not None and not players_df.empty:
            for player_id in player_ids:
                asset = live_draft_trade_evaluator.drafted_player_asset(
                    player_id, df_players=players_df, score_field=score_field
                )
                if asset is not None:
                    assets.append(asset)
        return assets

    send_assets = build_assets(body.send_pick_keys, body.send_player_ids)
    receive_assets = build_assets(body.receive_pick_keys, body.receive_player_ids)
    if not send_assets and not receive_assets:
        return {"ok": True, "reason": "assets_not_found", "stale_pick_keys": []}

    result = live_draft_trade_evaluator.evaluate_trade(send_assets=send_assets, receive_assets=receive_assets)

    return {
        "ok": True,
        "reason": "",
        "stale_pick_keys": [],
        "send_assets": [_project_live_draft_trade_asset(asset) for asset in result["send_assets"]],
        "receive_assets": [_project_live_draft_trade_asset(asset) for asset in result["receive_assets"]],
        "send_total": _clean_json_value(result["send_total"]),
        "receive_total": _clean_json_value(result["receive_total"]),
        "delta": _clean_json_value(result["delta"]),
        "verdict": result["verdict"],
    }


@app.get("/v1/leagues/{league_id}/my-roster")
def get_my_roster(
    league_id: str = Depends(resolve_league_path_id),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Identify which of this league's rosters belongs to the signed-in user.

    Always returns 200 with a `reason` the client can act on instead of
    parsing HTTP status semantics — see `_resolve_my_roster`.

    `league_id` is resolved forward across a Sleeper season rollover
    before this body ever runs (see resolve_league_path_id) -- this is the
    exact endpoint the 3rd real production repro of this bug (coridian_,
    2026-10-21) reproduced against: a stale saved league_id kept returning
    a full 200 with last season's frozen roster even after PR #1312.
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


def _project_portfolio_top_asset(item: Any) -> dict[str, Any] | None:
    """modules.dashboard_engine.build_league_summary's `top_asset` — the
    single highest-value-score player on a saved league's roster — trimmed
    to what the Portfolio share card's standout line needs (name + avatar +
    score). `None` when that league's roster summary had nothing to pick
    a top asset from (e.g. an empty roster, already an unreachable state
    upstream)."""

    if not isinstance(item, dict) or not item.get("player_id"):
        return None
    return {
        "player_id": _clean_json_value(item.get("player_id")),
        "name": _clean_json_value(item.get("name")),
        "position": _clean_json_value(item.get("position")),
        "team": _clean_json_value(item.get("team")),
        "tier": _clean_json_value(item.get("tier")),
        "score": _clean_json_value(item.get("score")),
    }


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


# A meaningful depth-chart move is at least one full spot (e.g. 2 -> 1) --
# anything smaller doesn't exist (depth_chart_order is an integer rank).
DEPTH_CHART_NOTE_MIN_DELTA = 1


def _project_depth_chart_note(row: pd.Series) -> str | None:
    """A plain-language note when this player's depth_chart_order moved at
    least one spot since the last players.db refresh (modules.
    depth_chart_history, written every 6h alongside the full rebuild).

    coridian_, 2026-10-19: "was there any way for us to predict (scenario)
    something like cam skattebo having 0 snaps and relaying that to
    USERS?" -- depth-chart movement is a leading indicator games-played/
    injury-status signals can't catch (a coaching-decision role change has
    no injury signal at all). ``None`` when there's no prior snapshot to
    compare against yet (first-ever run) or the move is too small to be
    worth stating -- same "state nothing rather than noise" contract as
    usage_trend's own gate just above.
    """

    delta = row.get("depth_chart_order_delta") if "depth_chart_order_delta" in row.index else None
    try:
        delta_value = int(delta) if delta is not None and pd.notna(delta) else 0
    except (TypeError, ValueError):
        delta_value = 0
    if abs(delta_value) < DEPTH_CHART_NOTE_MIN_DELTA:
        return None
    if delta_value > 0:
        return f"Moved up {delta_value} spot{'s' if delta_value != 1 else ''} on the depth chart since last week."
    return f"Moved down {abs(delta_value)} spot{'s' if abs(delta_value) != 1 else ''} on the depth chart since last week."


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
        # Same canonical player_tier column _project_ranking_row's "tier"
        # reads — never a fabricated/second tier scheme. Empty string (not
        # None) when the roster row genuinely has no tier on file, matching
        # this function's existing "" defaults for every other text field.
        "tier": str(item.get("player_tier") or "").strip(),
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
    (modules.league_display) and injury_ui.team_injury_display_note's
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
        # 0-99 "OVR" badge — see player_quick_view.overall_ratings_for_pool.
        # Computed by the caller over the full ranked pool (before any
        # limit=N truncation) and stashed on "_overall_rating_col" so this
        # row-at-a-time projector doesn't need its own copy of the pool.
        "overall_rating": _clean_json_value(row.get("_overall_rating_col")),
    }


@app.get("/v1/leagues/{league_id}/rankings")
def get_league_rankings(
    league_id: str = Depends(require_league_access),
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

    # Shares the (league_id, lens)-scoped cache every other list/detail
    # endpoint now pulls this exact pipeline from — see
    # league_value_settings.build_valued_players_frame_cached's docstring.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if valued.empty:
        return {"ok": True, "players": []}

    score_field = league_value_settings.valuation_score_field(lens)
    scoring_context = canonical_player_ranking.resolve_scoring_rank_context(settings)
    ranked = canonical_player_ranking.attach_canonical_ranks(
        valued,
        scoring_format=scoring_context.scoring_format,
        score_field=score_field,
        context=scoring_context,
    )

    # Computed on the full ranked pool (every eligible player at every
    # position), before the limit=N truncation below narrows it to the page
    # the client asked for — narrowing first would shrink/bias each
    # position's percentile pool by whatever the requested limit happened to
    # cut off. See player_quick_view.overall_ratings_for_pool.
    ranked["_overall_rating_col"] = player_quick_view.overall_ratings_for_pool(
        ranked, score_column=score_field
    )

    # Same "compute on the full pool before truncation" placement as the
    # overall-rating column above — Players' Madden-style stat sort/
    # percentile toggle needs raw stats + percentiles for every stat column,
    # not just the composite score. See
    # player_quick_view.annotate_rankings_stat_pool.
    ranked = player_quick_view.annotate_rankings_stat_pool(ranked)

    ranked = ranked.sort_values(score_field, ascending=False).head(limit)
    players = []
    for _, row in ranked.iterrows():
        projected = _project_ranking_row(row, score_field)
        projected["stats"] = player_quick_view.rankings_stat_entries_for_row(row)
        players.append(projected)
    return {"ok": True, "players": players}


@app.get("/v1/leagues/{league_id}/idp/values")
def get_league_idp_values(
    league_id: str = Depends(require_league_access),
    limit: int = 300,
    include_below: bool = False,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Individual-defensive-player values for leagues that start defenders.

    Leagues without DL/LB/DB/IDP_FLEX slots get ``{"idp": false, "players": []}``
    and are otherwise untouched. Values are model values on the same 0-10,000
    scale as offensive values (see docs/idp-model-backtest.md), scored with this
    league's own scoring_settings.
    """

    if not 1 <= limit <= 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000.")
    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    from modules import idp_league_values

    result = idp_league_values.cached_league_idp_values(league_id, league)
    body = {"ok": True, **result, "players": result["players"][:limit]}
    # Defenders projected below this league's replacement level (no value
    # above replacement) are opt-in: Trade Analyzer lists them with a dash.
    if not include_below:
        body.pop("below_replacement_players", None)
    return body


@app.get("/v1/leagues/{league_id}/players/{player_id}/rank")
def get_player_rank_in_league(
    player_id: str,
    league_id: str = Depends(require_league_access),
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

    # Same (league_id, lens)-scoped cache /rankings pulls from — Player
    # Detail hitting this per-player endpoint no longer re-runs the full
    # pool valuation pass it was only ever going to filter down to one row.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if valued.empty:
        return {"ok": True, "player": None}

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
    "profootballrumors.com": "Pro Football Rumors",
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


def _project_general_news_item(item: dict[str, Any]) -> dict[str, Any]:
    """Projects one modules.news.general_news_feed() item to GET /v1/news's
    response shape. That function already owns event_type/speculative/
    friendly-source projection and, when resolved, single- or two-player
    identity (matched_player* / matched_players — see its own docstring and
    modules.news._attach_general_news_player_identity) — this only adds the
    JSON field selection, never a second copy of that classification.
    """

    projected: dict[str, Any] = {
        "title": _clean_json_value(item.get("title")),
        "link": _clean_json_value(item.get("link")),
        "source": _clean_json_value(item.get("source")),
        "summary": _clean_json_value(my_news.build_quick_news_summary(item)),
        "published_ts": _clean_json_value(item.get("published_ts")),
        "event_type": _clean_json_value(item.get("event_type")),
        "speculative": bool(item.get("speculative")),
    }
    if item.get("matched_player_id"):
        projected["matched_player"] = _clean_json_value(item.get("matched_player"))
        projected["matched_player_id"] = _clean_json_value(item.get("matched_player_id"))
        projected["matched_player_position"] = _clean_json_value(item.get("matched_player_position"))
        projected["matched_player_team"] = _clean_json_value(item.get("matched_player_team"))
    matched_players = item.get("matched_players")
    if isinstance(matched_players, list) and len(matched_players) == 2:
        projected["matched_players"] = [
            {
                "matched_player": _clean_json_value(entry.get("matched_player")),
                "matched_player_id": _clean_json_value(entry.get("matched_player_id")),
                "matched_player_position": _clean_json_value(entry.get("matched_player_position")),
                "matched_player_team": _clean_json_value(entry.get("matched_player_team")),
            }
            for entry in matched_players
        ]
    return projected


@app.get("/v1/news")
def get_news(
    limit: int = 30,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Curated general NFL fantasy news (injury/role/transaction/off-field
    signal only — a generic headline is dropped). Not roster-scoped: this is
    a league-wide feed for anyone, not "your team's" news.

    Delegates the whole pipeline — disk-cached pool, actionable filtering,
    dedupe, sort, friendly source names, and single/two-player identity
    resolution — to modules.news.general_news_feed, the exact function the
    web app's own "News" route (app.py / modules.general_news_ui) calls, so
    this endpoint and that page share one curation implementation instead
    of two that can drift (this route previously re-implemented the pool/
    filter/dedupe/sort steps by hand). Never triggers a live RSS fetch on
    this request path — schedule_news_cache_refresh only starts a
    background refresh when the on-disk cache is already stale.
    """

    if not 1 <= limit <= MAX_NEWS_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_NEWS_LIMIT}.")

    news_cache.schedule_news_cache_refresh()
    items = news_cache.general_news_feed(limit)
    return {
        "ok": True,
        "items": [_project_general_news_item(item) for item in items],
        "status": news_cache.news_feed_status(),
    }


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


def _with_idp_trade_rows(
    valued: pd.DataFrame,
    idp_result: dict[str, Any] | None,
    score_field: str,
    wanted_ids: set[str],
) -> pd.DataFrame:
    """`valued` plus this league's defenders at their IDP-model value, so IDP
    players resolve as trade assets in an IDP league. A below-replacement
    defender is added (only when roster/asset-relevant) with value 0: it adds
    nothing to a package and clients show a dash. Non-IDP leagues, or any
    failure, return `valued` unchanged."""

    if not idp_result or not idp_result.get("idp"):
        return valued
    from modules import idp_roster_rows
    from modules.valuation_authority import (
        AUTHORITATIVE_COLUMN,
        SOURCE_COLUMN,
        STATUS_COLUMN,
        TRADE_ELIGIBLE_COLUMN,
    )

    have = set(valued["player_id"].astype(str)) if "player_id" in valued.columns else set()
    rows: list[dict[str, Any]] = []
    for entry in idp_roster_rows.trade_pool_rows(idp_result, wanted_ids):
        if str(entry["player_id"]) in have:
            continue
        value = entry.get("value")
        score = int(value) if isinstance(value, (int, float)) else 0
        rows.append(
            {
                "player_id": str(entry["player_id"]),
                "name": entry.get("name"),
                "position": entry.get("family"),
                "team": entry.get("team"),
                "age": entry.get("age"),
                "status": "Active",
                "injury_status": entry.get("injury_status"),
                "score": score,
                "value_score": score,
                "dynasty_score": score,
                "rebuild_score": score,
                score_field: score,
                STATUS_COLUMN: "model_derived",
                SOURCE_COLUMN: "idp_model",
                AUTHORITATIVE_COLUMN: True,
                TRADE_ELIGIBLE_COLUMN: True,
            }
        )
    if not rows:
        return valued
    return pd.concat([valued, pd.DataFrame(rows)], ignore_index=True, sort=False)


class TradeAnalyzerRequest(BaseModel):
    send_player_ids: list[str] = Field(default_factory=list)
    receive_player_ids: list[str] = Field(default_factory=list)
    # pick_id values from GET /v1/leagues/{id}/draft-picks
    # (f"{season}:{round}:{original_roster_id}").
    send_pick_ids: list[str] = Field(default_factory=list)
    receive_pick_ids: list[str] = Field(default_factory=list)
    # Any unrecognized value falls back to "retool" — see
    # modules.team_eval.normalize_team_strategy — so this is never rejected.
    strategy: str = trade_hub_engine.DEFAULT_ANALYZER_STRATEGY
    lens: str = "Dynasty"
    # Optional: the proposing partner's roster_id. When given, verdict.counter_action
    # can suggest a specific verified partner asset to ask for instead of just
    # generic guidance text — see modules.trade_offer_analyzer.build_counter_guidance.
    partner_roster_id: str = ""


def _league_waiver_pool(league_id: str, valued: pd.DataFrame) -> pd.DataFrame | None:
    """The league's real free agents (unrostered, waiver-actionable), valued
    like ``valued``. None when rosters cannot be read, so the lineup model
    falls back to the market replacement level rather than assuming an empty
    pool."""

    rosters = sleeper.get_rosters(league_id) or []
    if not rosters:
        return None
    roster_map = {str(r.get("roster_id")): list(r.get("players") or []) for r in rosters}
    rostered = {str(pid) for players in roster_map.values() for pid in players}
    pool = valued[~valued["player_id"].astype(str).isin(rostered)]
    if pool.empty:
        return pool
    from modules.player_state_authority import waiver_actionable_player_pool

    return waiver_actionable_player_pool(pool, roster_map, surface="trade_analyzer_lineup_hole")


def _lineup_hole_waiver_options(
    pool: pd.DataFrame | None, score_field: str, positions: set[str]
) -> dict[str, list[str]]:
    """Top real free agents (healthy, waiver-actionable) per position."""

    if pool is None or pool.empty or score_field not in pool.columns:
        return {}
    from modules.rankings import injury_level

    pool = pool.sort_values(score_field, ascending=False)
    out: dict[str, list[str]] = {}
    for pos in positions:
        names = [
            str(row.get("name"))
            for _, row in pool[pool["position"].astype(str).str.upper() == pos].iterrows()
            if row.get("name") and injury_level(str(row.get("status") or ""), str(row.get("injury_status") or "")) == "healthy"
        ][:3]
        if names:
            out[pos] = names
    return out


def _attach_projection_ppg(
    valued: pd.DataFrame, pool: pd.DataFrame | None, player_ids: set[str], score_field: str
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Attach the walk-forward weekly baseline (``proj_ppg``/``proj_sd``, PPR,
    availability not applied) to the players the lineup model will look at:
    the user's roster, the package, the partner, and the top free agents per
    position. Players with no usable weekly history simply get no column
    value; the model then labels its fallback basis. Never raises."""

    try:
        ids = set(player_ids)
        if pool is not None and not pool.empty and score_field in pool.columns:
            top = pool.sort_values(score_field, ascending=False).groupby(
                pool["position"].astype(str).str.upper(), sort=False
            ).head(25)
            ids |= {str(pid) for pid in top["player_id"].astype(str)}
        wanted = valued[valued["player_id"].astype(str).isin(ids)]
        baselines = player_projections.baseline_weekly_points(
            [{"player_id": str(r["player_id"]), "position": r.get("position")} for _, r in wanted.iterrows()]
        )
        if not baselines:
            return valued, pool

        def apply(frame: pd.DataFrame | None) -> pd.DataFrame | None:
            if frame is None or frame.empty:
                return frame
            frame = frame.copy()
            pids = frame["player_id"].astype(str)
            frame["proj_ppg"] = pids.map(lambda p: (baselines.get(p) or {}).get("ppg"))
            frame["proj_sd"] = pids.map(lambda p: (baselines.get(p) or {}).get("sd"))
            return frame

        return apply(valued), apply(pool)
    except Exception:
        return valued, pool


@app.post("/v1/leagues/{league_id}/trade-analyzer")
def post_trade_analyzer(
    body: TradeAnalyzerRequest,
    league_id: str = Depends(resolve_league_path_id),
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

    # Free accounts get FREE_WEEKLY_TRADE_EVAL_LIMIT evaluations per week
    # (modules.trade_eval_usage); web enforced it, this API did not. The
    # counter is server-side (Redis), not the user-writable user_settings.
    analyzer_user_id = str(user.get("id") or "")
    if not _manager_tendencies_gate(user):
        if not free_tier_ledger.consume_weekly_trade_eval(
            analyzer_user_id, trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT
        ):
            return {
                "ok": True,
                "verdict": None,
                "reason": "weekly_limit_reached",
                # Numbers for the clients' shared limit wall (lib/limitWall.ts):
                # the real constant and the real ledger reset, never copy.
                "limit": {
                    "limit": trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT,
                    "window": "week",
                    "resets_at": free_tier_ledger.next_weekly_reset().isoformat(),
                },
            }

    # Same (league_id, lens)-scoped cache /rankings and friends share — see
    # league_value_settings.build_valued_players_frame_cached's docstring.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=body.lens, players_db_path=PLAYERS_DB_PATH
    )
    if valued.empty:
        return {"ok": True, "verdict": None, "reason": "no_player_data"}

    score_field = league_value_settings.valuation_score_field(body.lens)
    # Same strategy-adjusted scale Trade Hub prices its ideas on
    # (trade_hub_engine.generate_trade_idea_records) and the web Trade
    # Analyzer already used, so a Hub idea and an Analyzer run of the same
    # package grade identically -- see modules.trade_grade.
    valued = trade_hub_engine.apply_strategy_age_curve(valued, body.strategy, score_field)
    pick_score_multiplier = trade_hub_engine.strategy_adjusted_pick_score_multiplier(1.0, body.strategy)

    # Keeper leagues: fold estimated keeper surplus into player values. Any
    # missing cost data (or failure) silently keeps the normal value.
    keeper_adjusted = False
    if settings.get("_keeper_mode"):
        try:
            current_picks, previous_picks = _keeper_draft_picks(league_id, league)
            adjusted = keepers_module.keeper_adjusted_values(
                valued=valued,
                score_field=score_field,
                num_teams=int(league.get("total_rosters") or (league.get("settings") or {}).get("num_teams") or 12),
                current_picks=current_picks,
                previous_picks=previous_picks,
                round_penalty=_stored_keeper_round_penalty(
                    auth_supabase.get_supabase_config(),
                    analyzer_user_id,
                    str(user.get("_access_token") or ""),
                    league_id,
                ),
            )
            if adjusted:
                valued = keepers_module.apply_keeper_values(valued, score_field, adjusted)
                keeper_adjusted = True
        except Exception:
            keeper_adjusted = False

    my_roster_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    # IDP leagues: defenders resolve as assets at their model value. Trust
    # gating below keeps untrusted ones out of any counter-offer suggestion.
    idp_result = _league_idp_result(league_id, league) if settings.get("idp_slots") else None
    idp_ids: set[str] = set()
    trusted_idp: set[str] = set()
    untrusted_idp: set[str] = set()
    if idp_result and idp_result.get("idp"):
        from modules import idp_roster_rows

        valued = _with_idp_trade_rows(
            valued,
            idp_result,
            score_field,
            my_roster_ids | {str(p) for p in body.send_player_ids + body.receive_player_ids},
        )
        idp_ids = idp_roster_rows.all_idp_ids(idp_result)
        trusted_idp = idp_roster_rows.trusted_idp_ids(idp_result)
        untrusted_idp = idp_ids - trusted_idp
    # Trade engine v2 inputs: the league's real free-agent pool (what you
    # could pick up instead) and the weekly projection baseline for every
    # player the lineup model will look at. Both degrade to documented
    # fallbacks (market replacement level, season average, value estimate).
    try:
        waiver_pool = _league_waiver_pool(league_id, valued)
    except Exception:
        waiver_pool = None
    valued, waiver_pool = _attach_projection_ppg(
        valued,
        waiver_pool,
        my_roster_ids
        | {str(p) for p in body.send_player_ids + body.receive_player_ids}
        | {
            str(pid)
            for roster in (sleeper.get_rosters(league_id) if body.partner_roster_id else [])
            if str(roster.get("roster_id")) == str(body.partner_roster_id)
            for pid in (roster.get("players") or [])
        },
        score_field,
    )
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
        # Cached (30s live-time bucket) — the counter-package fallback
        # below can call this exact (league_id, lens) computation again
        # within the SAME request (send/receive picks present AND an
        # unfavorable verdict), which used to mean running this full
        # per-roster pass twice for identical inputs in one response.
        pick_summary, _ = league_rankings.build_league_summary_and_draft_capital_cached(
            league_id=league_id, lens=body.lens, players_db_path=PLAYERS_DB_PATH
        )
        if not pick_summary.empty:
            crowd_class_strength = (
                college_scouting.get_cached_crowd_class_strength_by_year(
                    auth_supabase.get_supabase_config(), str(user.get("_access_token") or "")
                )
                if college_scouting.class_strength_signal_enabled()
                else {}
            )
            all_picks = trade_ideas.list_draft_pick_assets(
                league_id,
                pick_summary,
                league_settings=settings,
                crowd_class_strength_by_year=crowd_class_strength,
            )
            picks_by_id = {
                f"{pick.get('season')}:{pick.get('round')}:{pick.get('original_roster_id')}": pick
                for pick in all_picks
            }

            def resolve_picks(pick_ids: list[str]) -> list[dict[str, Any]]:
                return [
                    pick_asset_from_mapping(picks_by_id[pick_id], pick_score_multiplier=pick_score_multiplier)
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
                # Counter suggestions never lean on a defender the IDP model
                # is not confident about.
                if str(row.get("player_id")) not in untrusted_idp
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
        waiver_df=waiver_pool,
    )
    if not fit or not fit.get("available"):
        return {"ok": True, "verdict": None, "reason": "fit_unavailable"}

    # A critical this-week lineup hole ("no startable RB") gets concrete
    # free-agent options in its fix guidance: real, unowned, healthy players.
    waiver_options: dict[str, list[str]] = {}
    critical_positions = {
        str(w.get("position") or "")
        for w in (fit.get("lineup_warnings") or [])
        if w.get("severity") == "critical" and w.get("position")
    }
    model_hole = ((fit.get("lineup_model") or {}).get("worst_position")) or ""
    hole_positions = set(critical_positions) | ({model_hole} if model_hole else set())
    if hole_positions:
        try:
            waiver_options = _lineup_hole_waiver_options(waiver_pool, score_field, hole_positions)
        except Exception:
            waiver_options = {}

    verdict = trade_offer_analyzer.decide_offer_verdict(
        fit,
        send_assets=send_assets,
        receive_assets=receive_assets,
        partner_assets=partner_assets,
        waiver_options=waiver_options,
    )

    if getattr(verdict, "band", None) in trade_offer_analyzer.COUNTER_PACKAGE_BANDS:
        # Real alternate packages only get built for an unfavorable verdict,
        # and only reuse assets the two rosters actually hold — never a
        # second, invented valuation. Any failure here (e.g. no picks data
        # for this league) just falls back to the existing text-only
        # counter_guidance already on `verdict`.
        try:
            my_asset_pool: list[dict[str, Any]] = [
                player_asset_from_mapping(row, score_field=score_field)
                for _, row in my_team_df.iterrows()
                if str(row.get("player_id")) not in untrusted_idp
            ]
            partner_asset_pool: list[dict[str, Any]] = list(partner_assets)
            # Same cached front door as the send/receive-picks branch above
            # — same (league_id, lens) question, so a request that hits
            # both branches (picks proposed AND an unfavorable verdict)
            # shares one cache entry instead of recomputing this twice.
            pick_summary, _ = league_rankings.build_league_summary_and_draft_capital_cached(
                league_id=league_id, lens=body.lens, players_db_path=PLAYERS_DB_PATH
            )
            if not pick_summary.empty:
                my_roster_id_str = str(my_roster.get("roster_id") or "")
                for pick in trade_ideas.list_draft_pick_assets(
                    league_id, pick_summary, league_settings=settings
                ):
                    owner = str(pick.get("owner_roster_id") or "")
                    if owner == my_roster_id_str:
                        my_asset_pool.append(pick_asset_from_mapping(pick, pick_score_multiplier=pick_score_multiplier))
                    elif body.partner_roster_id and owner == str(body.partner_roster_id):
                        partner_asset_pool.append(pick_asset_from_mapping(pick, pick_score_multiplier=pick_score_multiplier))

            my_needs = trade_analyzer_fit.get_needed_positions(my_team_df, None, settings)
            # Positions the trade would leave empty this week rank first when
            # looking for a partner piece to ask for.
            my_needs = list(dict.fromkeys([*sorted(hole_positions), *my_needs]))

            def _regrade_counter_package(cand_send, cand_receive):
                cand_fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
                    my_team_df=my_team_df,
                    all_players_df=valued,
                    send_assets=cand_send,
                    receive_assets=cand_receive,
                    metrics=None,
                    strategy=body.strategy,
                    lineup_settings=settings,
                    score_field=score_field,
                    waiver_df=waiver_pool,
                )
                if not cand_fit or not cand_fit.get("available"):
                    return None
                return trade_offer_analyzer.decide_offer_verdict(
                    cand_fit,
                    send_assets=cand_send,
                    receive_assets=cand_receive,
                    partner_assets=partner_asset_pool,
                    waiver_options=waiver_options,
                )

            alternate_packages = trade_offer_analyzer.build_counter_offer_packages(
                band=verdict.band,
                value_delta=verdict.trade_score,
                send_assets=send_assets,
                receive_assets=receive_assets,
                my_asset_pool=my_asset_pool,
                partner_asset_pool=partner_asset_pool,
                regrade=_regrade_counter_package,
                my_needs=my_needs,
            )
            if alternate_packages:
                verdict = verdict.with_alternate_packages(alternate_packages)
        except Exception:
            pass

    # Trade Analyzer stays fully usable after the trade deadline — it's the
    # offseason-planning tool — but says so instead of implying the trade
    # can be sent today (modules.league_calendar).
    trade_window = league_calendar.trade_window(league)
    verdict_public = verdict.to_public_dict()
    return {
        "ok": True,
        "verdict": verdict_public,
        "reason": "",
        "keeper_adjusted": keeper_adjusted,
        "trade_window": trade_window,
        # Read-only description of what this verdict assumed (format, lens,
        # posture, projections vs values, injury timing); see
        # modules.verdict_assumptions. Never feeds back into the verdict.
        "assumptions": verdict_assumptions.build_verdict_assumptions(
            lens=body.lens,
            settings=settings,
            strategy=body.strategy,
            keeper_adjusted=keeper_adjusted,
            has_picks=bool(send_pick_assets or receive_pick_assets),
            lineup_model=verdict_public.get("lineup_model") if isinstance(verdict_public, dict) else None,
        ),
        "planning_note": " ".join(
            note
            for note in (
                league_calendar.TRADE_ANALYZER_DEADLINE_NOTE if trade_window["trade_deadline_passed"] else "",
                "Values include estimated keeper surplus." if keeper_adjusted else "",
            )
            if note
        ),
    }


@app.get("/v1/leagues/{league_id}/recap")
def get_league_recap(
    league_id: str = Depends(require_league_access),
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

    # Same (league_id, lens)-scoped cache /rankings and friends share — see
    # league_value_settings.build_valued_players_frame_cached's docstring.
    # Recap's lookup only ever needs the Dynasty lens, matching this
    # endpoint's prior hardcoded "Dynasty" argument.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens="Dynasty", players_db_path=PLAYERS_DB_PATH
    )
    lookup_rows: list[dict[str, Any]] = []
    if not valued.empty:
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


@app.get("/v1/leagues/{league_id}/history")
def get_league_history(
    league_id: str = Depends(require_league_access),
    season_league_id: str | None = None,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """League transaction timeline — completed trades, waiver claims,
    free-agent adds, and pick changes, each with the same retrospective
    letter grade the web app's League Recaps -> History tab shows (shares
    modules.league_history's normalization and modules.transaction_grades'
    grading verbatim; no scoring math lives here).

    `season_league_id` selects one entry from the Sleeper
    previous_league_id chain (defaults to `league_id`, the current season).
    `seasons` is always returned so the client can build a season picker
    without a second round trip.
    """

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    chain = league_history.walk_season_chain(league_id, sleeper.get_league)
    if not chain:
        return {
            "ok": True,
            "seasons": [],
            "selected_league_id": league_id,
            "transactions": [],
            "reason": "no_history",
        }

    chain_ids = {str(item.get("league_id")) for item in chain}
    selected_league_id = (
        str(season_league_id)
        if season_league_id and str(season_league_id) in chain_ids
        else league_id
    )

    history_payload = league_history.collect_season_transactions(
        selected_league_id,
        fetch_league=sleeper.get_league,
        fetch_transactions=sleeper.get_transactions,
    )
    profiles = sleeper.get_league_roster_profiles(selected_league_id) or {}

    # Same (league_id, lens)-scoped valuation cache /recap and /rankings
    # already share — see league_value_settings.build_valued_players_frame_cached.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=selected_league_id, lens="Dynasty", players_db_path=PLAYERS_DB_PATH
    )
    lookup_rows: list[dict[str, Any]] = []
    if not valued.empty:
        cols = [c for c in ("player_id", "name", "position", "team", "value_score") if c in valued.columns]
        if cols:
            lookup_rows = valued[cols].to_dict("records")
    player_lookup = league_history.player_lookup_from_rows(lookup_rows)

    normalized = league_history.normalize_season_payload(
        history_payload, profiles=profiles, player_lookup=player_lookup
    )

    # Same current_week the web route passes into cached_transaction_grades
    # (league_recaps.last_scored_week of the home/current league), kept
    # constant across a season switch — grading "how recent is this" is
    # always relative to now, not to whichever past season is being browsed.
    current_week = league_recaps.last_scored_week(league)
    for item in normalized:
        event_id = item.get("transaction_id")
        later_events = [
            other
            for other in normalized
            if other.get("transaction_id") != event_id
            and int(other.get("timestamp") or 0) > int(item.get("timestamp") or 0)
        ]
        item["grade"] = transaction_grades.grade_transaction(
            item,
            player_lookup=player_lookup,
            current_week=current_week,
            later_events=later_events,
        )

    seasons = [
        {
            "league_id": item.get("league_id"),
            "season": item.get("season"),
            "name": item.get("name"),
        }
        for item in chain
    ]

    return {
        "ok": True,
        "seasons": seasons,
        "selected_league_id": selected_league_id,
        "transactions": normalized,
        "reason": "",
    }


@app.get("/v1/leagues/{league_id}/storylines")
def get_league_storylines(
    league_id: str = Depends(require_league_access),
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Season-long storyline awards — shares the exact same builder as the
    web app's League Recaps -> Storylines tab (modules.league_storylines.
    build_league_storylines). Does not invent new awards or recompute any
    metric here; it only assembles the same normalized transaction history
    the web route reads off modules.league_history and hands it to the real
    engine.

    Scoped to the current season only (`league_id`'s own transactions), the
    same scope the web route's cached_season_history_payload uses for this
    tab -- unlike /history, this endpoint does not walk the prior-season
    chain.
    """

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    season = str(league.get("season") or "")
    history_payload = league_history.collect_season_transactions(
        league_id,
        fetch_league=sleeper.get_league,
        fetch_transactions=sleeper.get_transactions,
    )
    profiles = sleeper.get_league_roster_profiles(league_id) or {}

    # Same (league_id, lens)-scoped valuation cache /recap and /history
    # already share — see league_value_settings.build_valued_players_frame_cached.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens="Dynasty", players_db_path=PLAYERS_DB_PATH
    )
    lookup_rows: list[dict[str, Any]] = []
    if not valued.empty:
        cols = [c for c in ("player_id", "name", "position", "team", "value_score") if c in valued.columns]
        if cols:
            lookup_rows = valued[cols].to_dict("records")
    player_lookup = league_history.player_lookup_from_rows(lookup_rows)

    normalized = league_history.normalize_season_payload(
        history_payload, profiles=profiles, player_lookup=player_lookup
    )
    report = league_storylines.build_league_storylines(
        normalized, profiles=profiles, season=season
    )
    return {"ok": True, "storylines": report, "reason": ""}


_MANAGER_TENDENCIES_UPSELL = {
    "title": "How every manager in your league trades",
    "body": (
        "Manager Tendencies is a Premium feature: each manager's real trade "
        "and waiver history across past seasons, with the trades behind "
        "every read. Upgrade to Premium to unlock it."
    ),
}


def _manager_tendencies_gate(user: dict[str, Any]) -> bool:
    """Premium (PRO) gate, same tier and same check as GM Plan / Live Draft
    / the full League Pulse and Trade Hub lists. Checked before any Sleeper
    scan so a Free caller never pays for the multi-season transaction read."""

    user_id = str(user.get("id") or "")
    if not user_id:
        return False
    config = auth_supabase.get_supabase_config()
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or ""))
    return premium.is_at_least(profile.get("entitlement"), premium.PRO)


_PLAYOFF_ODDS_UPSELL = {
    "title": "Your real shot at the playoffs",
    "body": (
        "Playoff Odds is a Pro feature: a rest-of-season simulation of your "
        "league's real schedule, every team's playoff chance and projected "
        "seed. Start your free trial to unlock it."
    ),
}
_DRAFT_CENTER_UPSELL = {
    "title": "Know where you stand on draft capital",
    "body": (
        "Draft Center is a Pro feature: your draft posture, league-wide "
        "pick decision signals and the best trade partners for your picks. "
        "Start your free trial to unlock it."
    ),
}
_COLLEGE_SCOUTING_UPSELL = {
    "title": "Scout the next rookie class",
    "body": (
        "College Scouting is a Pro feature: the shared prospect board, "
        "community grades, your own scouting reports and watchlist. "
        "Start your free trial to unlock it."
    ),
}


def _is_pro_caller(user: dict[str, Any]) -> bool:
    """Server-side Pro check for Playoff Odds / Draft Center / College
    Scouting (owner decision 2026-10-23). Trialing accounts are stored as
    Pro, so they pass. Checked before any computation or catalog read."""

    return _manager_tendencies_gate(user)


@app.get("/v1/leagues/{league_id}/managers/tendencies")
def get_league_manager_tendencies(
    league_id: str = Depends(require_league_access),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """League-wide Manager Tendencies summary: one short, evidence-backed
    line per manager plus each signal's label (modules.manager_tendencies).
    Built from the league's real Sleeper transactions across its
    previous_league_id season chain; managers below a signal's minimum
    sample get "Not enough trades yet" rather than a guessed label."""

    if not _manager_tendencies_gate(user):
        return {
            "ok": True,
            "reason": "",
            "is_premium": False,
            "upsell": _MANAGER_TENDENCIES_UPSELL,
            "managers": [],
            "seasons": [],
        }
    if not sleeper.get_league(league_id):
        raise HTTPException(status_code=404, detail="League not found.")
    profile = manager_tendencies.league_tendencies_cached(league_id)
    return {
        "ok": True,
        "reason": "" if profile.get("managers") else "no_history",
        "is_premium": True,
        "upsell": None,
        "league_id": league_id,
        "seasons": profile.get("seasons") or [],
        "league": profile.get("league") or {},
        "managers": manager_tendencies.league_summary(profile),
    }


@app.get("/v1/leagues/{league_id}/managers/{roster_id}/tendencies")
def get_manager_tendencies(
    roster_id: int,
    league_id: str = Depends(require_league_access),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """One manager's full Manager Tendencies profile: every signal with its
    value, sample size, minimum sample, and evidence (transaction ids),
    plus the referenced transactions themselves so each read can be checked
    against the real trades. Same data, cache, and gate as the league
    summary above."""

    if not _manager_tendencies_gate(user):
        return {
            "ok": True,
            "reason": "",
            "is_premium": False,
            "upsell": _MANAGER_TENDENCIES_UPSELL,
            "manager": None,
            "transactions": {},
        }
    if not sleeper.get_league(league_id):
        raise HTTPException(status_code=404, detail="League not found.")
    profile = manager_tendencies.league_tendencies_cached(league_id)
    detail = manager_tendencies.manager_detail(profile, int(roster_id))
    if detail is None:
        raise HTTPException(status_code=404, detail="Roster not found in this league.")
    player_lookup: dict[str, dict[str, Any]] = {}
    current_week = 0
    if (detail["manager"] or {}).get("recent_trade_refs"):
        # Same cached valuation frame + last_scored_week the History tab
        # grades with; a failure just leaves the grades null.
        try:
            valued = league_value_settings.build_valued_players_frame_cached(
                league_id=league_id, lens="Dynasty", players_db_path=PLAYERS_DB_PATH
            )
            if not valued.empty:
                cols = [c for c in ("player_id", "name", "position", "team", "value_score") if c in valued.columns]
                player_lookup = league_history.player_lookup_from_rows(valued[cols].to_dict("records"))
            current_week = league_recaps.last_scored_week(sleeper.get_league(league_id))
        except Exception:
            player_lookup, current_week = {}, 0
    return {
        "ok": True,
        "reason": "",
        "is_premium": True,
        "upsell": None,
        "league_id": league_id,
        "seasons": profile.get("seasons") or [],
        "league": profile.get("league") or {},
        "thresholds": profile.get("thresholds") or {},
        "manager": detail["manager"],
        "transactions": detail["transactions"],
        "recent_trades": manager_tendencies.recent_trades(
            profile, int(roster_id), player_lookup=player_lookup, current_week=current_week
        ),
    }


def _alert_key_for_link(link: str) -> str:
    """Stable, opaque identity for one alert item — a hash of its article
    link, never the raw URL or any football output (see
    docs/supabase_mobile_alert_reads.sql)."""

    return hashlib.sha256(str(link or "").encode("utf-8")).hexdigest()[:32]


def _alert_key_for_item(item: dict[str, Any]) -> str:
    """The cross-device identity of one alert row.

    Every client (web, the current mobile build, and future builds) reads
    this exact value back from GET .../alerts and posts it to
    POST .../alerts/read, so it must be a pure function of the underlying
    article, never of the request, device, or time. RSS ingestion
    (modules.news._entry_to_item) already drops linkless entries, so in
    practice this is always the article-link hash existing read rows were
    written under. The fallback only guards against a future linkless
    source: without it every linkless item would hash "" and share ONE key,
    so reading any of them would mark all of them read.
    """

    link = str(item.get("link") or "")
    if link:
        return _alert_key_for_link(link)
    identity = "|".join(
        str(item.get(field) or "").strip()
        for field in ("title", "source", "published_ts", "matched_player")
    )
    return _alert_key_for_link(f"nolink:{identity}")


def _alert_read_league_ids(*league_ids: str) -> list[str]:
    """Distinct, non-empty league ids, order preserved."""

    seen: list[str] = []
    for value in league_ids:
        clean = str(value or "").strip()
        if clean and clean not in seen:
            seen.append(clean)
    return seen


def _fetch_read_alert_keys(
    config: dict, user_id: str, access_token: str, league_id: str | list[str]
) -> set[str]:
    """Which alert_keys this user has already marked read in this league.

    `league_id` may be a list: GET .../alerts passes both the raw path id
    and its season-rollover-resolved id, because POST .../alerts/read is
    called by whichever device happens to hold whichever id (a phone with
    an older saved-league id, the web with the current one). Reading both
    keeps one device's reads visible on the other.

    Fails closed to "none read" (never crashes the alerts feed) — covers
    the pre-migration state where mobile_alert_reads doesn't exist yet.
    """

    if not user_id:
        return set()
    league_ids = _alert_read_league_ids(*(league_id if isinstance(league_id, list) else [league_id]))
    if not league_ids:
        return set()
    if len(league_ids) == 1:
        league_filter = f"league_id=eq.{league_ids[0]}"
    else:
        quoted = ",".join('"' + value.replace('"', "") + '"' for value in league_ids)
        league_filter = f"league_id=in.({quoted})"
    url = auth_supabase.rest_api_url(
        config,
        "mobile_alert_reads",
        f"select=alert_key&user_id=eq.{user_id}&{league_filter}",
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


def _roster_reserve_taxi_ids(roster: dict[str, Any]) -> tuple[set[str], set[str]]:
    """(reserve_ids, taxi_ids) — the two Sleeper roster slots that sit
    outside the normal starter/bench lineup, as string player ids.

    Shared by `_roster_relationship_map` (Alerts' roster-relationship pill)
    and `_suggested_lineup_split` (My Team's bench `roster_slot` tag) so
    both read Sleeper's real IR/taxi placement the exact same way instead
    of each re-deriving it from the raw roster payload.
    """

    reserve = {str(pid) for pid in (roster.get("reserve") or []) if pid}
    taxi = {str(pid) for pid in (roster.get("taxi") or []) if pid}
    return reserve, taxi


def _roster_slot_for_player(
    player_id: str, *, reserve_ids: set[str], taxi_ids: set[str], is_starter: bool
) -> str:
    """"starter"|"bench"|"taxi"|"ir" for one rostered player.

    Sleeper's real reserve/taxi placement always wins over starter/bench —
    a manager can genuinely start an IR-tagged player, but the roster-slot
    concept this resolves is about WHERE they parked him, not the lineup
    optimizer's opinion. `is_starter` is Sleeper's own `starters` list for
    `_roster_relationship_map`, or `suggest_optimal_lineup`'s
    `suggested_starter` flag for `_suggested_lineup_split` — either way,
    this is the one place reserve/taxi precedence is decided.
    """

    if player_id in reserve_ids:
        return "ir"
    if player_id in taxi_ids:
        return "taxi"
    return "starter" if is_starter else "bench"


def _roster_relationship_map(roster: dict[str, Any]) -> dict[str, str]:
    """player_id -> "starter"|"bench"|"taxi"|"ir" for every rostered player.

    Sleeper's own roster payload already separates these (players/starters/
    taxi/reserve) — no lineup computation needed, this just reads the
    league's actual current state, not a suggested optimal lineup.
    """

    starters = {str(pid) for pid in (roster.get("starters") or []) if pid}
    reserve_ids, taxi_ids = _roster_reserve_taxi_ids(roster)
    players = {str(pid) for pid in (roster.get("players") or []) if pid}

    return {
        player_id: _roster_slot_for_player(
            player_id, reserve_ids=reserve_ids, taxi_ids=taxi_ids, is_starter=player_id in starters
        )
        for player_id in players
    }


def _project_alert_item(
    item: dict[str, Any],
    *,
    read_keys: set[str],
    player_ids_by_name: dict[str, str],
    player_info_by_id: dict[str, dict[str, Any]],
    roster_relationship: dict[str, str],
) -> dict[str, Any]:
    payload = _project_news_item(item)
    alert_key = _alert_key_for_item(item)
    payload["alert_key"] = alert_key
    payload["read"] = alert_key in read_keys
    matched_player = str(item.get("matched_player") or "")
    matched_player_id = player_ids_by_name.get(matched_player)
    payload["matched_player"] = _clean_json_value(item.get("matched_player"))
    payload["matched_player_id"] = matched_player_id
    # Sourced from the same roster slice player_ids_by_name comes from — not
    # a fresh lookup — so a name-matched player absent from the current
    # roster (already-dropped, etc.) just falls back to None below rather
    # than fabricating a position/team/tier.
    player_info = player_info_by_id.get(matched_player_id or "") or {}
    payload["matched_player_position"] = player_info.get("position")
    payload["matched_player_team"] = player_info.get("team")
    payload["matched_player_tier"] = player_info.get("tier")
    payload["relevance_reason"] = _clean_json_value(item.get("relevance_reason"))
    payload["roster_relationship"] = roster_relationship.get(matched_player_id or "")
    return payload


@app.get("/v1/leagues/{league_id}/alerts")
def get_league_alerts(
    request: Request,
    league_id: str = Depends(resolve_league_path_id),
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
    # One pass over the roster slice builds both lookups (previously two
    # separate .iterrows() passes over the same frame).
    player_ids_by_name: dict[str, str] = {}
    player_info_by_id: dict[str, dict[str, Any]] = {}
    for _, row in mine.iterrows():
        player_id = str(row.get("player_id") or "").strip()
        name = str(row.get("name") or "").strip()
        if name:
            player_ids_by_name[name] = player_id
        if player_id:
            player_info_by_id[player_id] = {
                "position": _clean_json_value(row.get("position")),
                "team": _clean_json_value(row.get("team")),
                "tier": _clean_json_value(row.get("player_tier")),
            }

    news_cache.schedule_news_cache_refresh()
    pool = news_cache.load_cached_news_pool()
    filtered = my_news.filter_news_for_players(pool, player_names, roster_teams)
    curated = my_news.curate_player_news(filtered, max_items=limit)

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    # Raw path id AND resolved id: see _fetch_read_alert_keys' docstring.
    raw_league_id = str(request.path_params.get("league_id") or "")
    read_keys = _fetch_read_alert_keys(
        config,
        user_id,
        str(user.get("_access_token") or ""),
        _alert_read_league_ids(league_id, raw_league_id),
    )
    roster_relationship = _roster_relationship_map(my_roster)

    items = [
        _project_alert_item(
            item,
            read_keys=read_keys,
            player_ids_by_name=player_ids_by_name,
            player_info_by_id=player_info_by_id,
            roster_relationship=roster_relationship,
        )
        for item in curated
    ]
    return {"ok": True, "items": items, "reason": ""}


class MarkAlertReadRequest(BaseModel):
    alert_key: str


@app.post("/v1/leagues/{league_id}/alerts/read")
def mark_league_alert_read(
    body: MarkAlertReadRequest,
    # NOT resolved via Depends (see resolve_league_path_id's docstring): the
    # row for the exact id the client sent is always written. The body
    # below ALSO writes the resolved id's row when a season rollover makes
    # them differ, so a read made on a device holding the old id still
    # shows as read on a device holding the new one (GET .../alerts reads
    # both ids). alert_key is an article hash, not league data, so the
    # extra row can never mark a different alert read.
    league_id: str,
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

    league_ids = _alert_read_league_ids(league_id, resolve_league_path_id(league_id, user))
    rows = [{"user_id": user_id, "league_id": value, "alert_key": alert_key} for value in league_ids]
    url = auth_supabase.rest_api_url(config, "mobile_alert_reads")
    headers = auth_supabase.auth_headers(config, str(user.get("_access_token") or ""))
    headers["Prefer"] = "resolution=ignore-duplicates,return=minimal"
    try:
        response = requests.post(
            url,
            headers=headers,
            # One object for the common case (no rollover) — exactly the
            # shape every existing caller/test already sends; an array
            # (PostgREST bulk insert) only when the two ids differ.
            json=rows[0] if len(rows) == 1 else rows,
            timeout=15,
        )
    except Exception:
        return {"ok": False, "reason": "not_available"}
    if response.status_code >= 400:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


# ---------------------------------------------------------------------------
# Guess the Player ("Whose stats are these?") — Dashboard mini-game.
# coridian_, 2026-10-19 (confirmed spec, via Discord): one real player's
# real recent stat line, name/photo hidden, multiple-choice reveal, a real
# persisted streak (docs/supabase_guess_the_player.sql). The actual
# selection/distractor logic lives in modules.guess_the_player — this is
# just auth, caching, and streak read/write.
# ---------------------------------------------------------------------------

_GUESS_THE_PLAYER_CACHE_TTL_SECONDS = 24 * 60 * 60


def _guess_the_player_today() -> str:
    """A UTC calendar date, not local time — so the featured pick can never
    disagree between callers in different timezones hitting the same
    always-on backend instance."""

    return datetime.now(timezone.utc).date().isoformat()


def _guess_the_player_compute_pick(today: str) -> dict[str, Any] | None:
    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        return None
    season_stats = sleeper.get_season_player_stats()
    if not season_stats:
        return None
    return guess_the_player.build_daily_pick(players_df, season_stats, seed=today)


def _guess_the_player_daily_pick(today: str) -> dict[str, Any] | None:
    """Today's featured (player, week) pick.

    Identical across every backend worker/process for the same `today`
    even WITHOUT this cache — modules.guess_the_player.build_daily_pick
    seeds its own randomness off `today`, not off call order — so this
    cache exists purely to avoid repeating the full players-table scan on
    every request, same fail-open contract as redis_single_flight_cache's
    other callers (e.g. _fetch_saved_leagues_cached above).
    """

    cache_key = redis_cache.build_cache_key("guess_the_player_daily_pick", today)
    try:
        return redis_cache.redis_single_flight_cache(
            cache_key=cache_key,
            ttl_seconds=_GUESS_THE_PLAYER_CACHE_TTL_SECONDS,
            compute=lambda: _guess_the_player_compute_pick(today),
        )
    except Exception:
        return _guess_the_player_compute_pick(today)


def _guess_the_player_public_prompt(pick: dict[str, Any]) -> dict[str, Any]:
    """The hidden-identity payload GET actually returns — the real
    player's name/team/player_id never appear outside the shuffled
    `options` list, indistinguishable there from the real distractors."""

    return {
        "pick_id": pick["pick_id"],
        "season": pick["season"],
        "week": pick["week"],
        "position": pick["position"],
        "tier": pick["tier"],
        "stat_line": pick["stat_line"],
        "fantasy_points_ppr": pick["fantasy_points_ppr"],
        "options": [dict(option) for option in pick["options"]],
    }


def _guess_the_player_streak_int(row: dict[str, Any] | None, key: str) -> int:
    if not row:
        return 0
    try:
        return int(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _guess_the_player_streak_payload(row: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "current_streak": _guess_the_player_streak_int(row, "current_streak"),
        "best_streak": _guess_the_player_streak_int(row, "best_streak"),
    }


def _guess_the_player_correct_identity(pick: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": pick["player_id"],
        "name": pick["name"],
        "team": pick["team"],
        "position": pick["position"],
        "tier": pick["tier"],
    }


@app.get("/v1/guess-the-player")
def get_guess_the_player(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Today's "Whose stats are these?" pick plus the caller's real,
    persisted streak. League-independent — one shared pick per calendar
    day for every signed-in user.
    """

    today = _guess_the_player_today()
    pick = _guess_the_player_daily_pick(today)
    if pick is None:
        return {
            "ok": True,
            "available": False,
            "reason": "no_surprising_player_today",
            "prompt": None,
            "already_answered": False,
            "last_result": None,
            "correct_player": None,
            "streak": {"current_streak": 0, "best_streak": 0},
        }

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    streak_row, _ = account_store.fetch_guess_the_player_streak(
        config, str(user.get("_access_token") or ""), user_id=user_id
    )
    already_answered = bool(streak_row) and str(streak_row.get("last_pick_id") or "") == pick["pick_id"]
    last_result = str(streak_row.get("last_result") or "").strip() if already_answered else ""

    return {
        "ok": True,
        "available": True,
        "reason": "",
        "prompt": _guess_the_player_public_prompt(pick),
        "already_answered": already_answered,
        "last_result": last_result or None,
        # Only revealed once this user has genuinely already answered
        # TODAY's pick — never alongside an unanswered prompt, which would
        # leak the answer before a real guess.
        "correct_player": _guess_the_player_correct_identity(pick) if already_answered else None,
        "streak": _guess_the_player_streak_payload(streak_row),
    }


class GuessThePlayerAnswerRequest(BaseModel):
    pick_id: str
    player_id: str


@app.post("/v1/guess-the-player/answer")
def answer_guess_the_player(
    body: GuessThePlayerAnswerRequest, user: dict[str, Any] = Depends(require_user)
) -> dict[str, Any]:
    """Score one guess against today's real pick and durably update the
    caller's streak (docs/supabase_guess_the_player.sql).

    Idempotent per pick_id: resubmitting the SAME day's pick_id (reload,
    double-tap, retried request) replays the already-recorded result
    instead of re-scoring — a streak can only move once per real daily
    pick, never inflate from a repeat submission.
    """

    pick_id = str(body.pick_id or "").strip()
    guessed_player_id = str(body.player_id or "").strip()
    if not pick_id or not guessed_player_id:
        raise HTTPException(status_code=422, detail="pick_id and player_id are required.")

    today = _guess_the_player_today()
    pick = _guess_the_player_daily_pick(today)
    if pick is None or pick["pick_id"] != pick_id:
        # The day rolled over (or the cache rotated) between the client's
        # fetch and this submission — fail closed with a reason the client
        # can react to (refetch today's pick) rather than scoring against
        # stale or mismatched data.
        raise HTTPException(status_code=409, detail="This pick has expired. Refresh and try again.")

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    streak_row, _ = account_store.fetch_guess_the_player_streak(config, access_token, user_id=user_id)

    if streak_row and str(streak_row.get("last_pick_id") or "") == pick_id:
        correct = str(streak_row.get("last_result") or "").strip() == "correct"
        return {
            "ok": True,
            "already_answered": True,
            "correct": correct,
            "correct_player": _guess_the_player_correct_identity(pick),
            "streak": _guess_the_player_streak_payload(streak_row),
        }

    correct = guessed_player_id == pick["player_id"]
    current_streak = _guess_the_player_streak_int(streak_row, "current_streak")
    best_streak = _guess_the_player_streak_int(streak_row, "best_streak")
    new_current = current_streak + 1 if correct else 0
    new_best = max(best_streak, new_current)

    ok, _ = account_store.upsert_guess_the_player_streak(
        config,
        access_token,
        {
            "user_id": user_id,
            "current_streak": new_current,
            "best_streak": new_best,
            "last_pick_id": pick_id,
            "last_result": "correct" if correct else "incorrect",
        },
    )
    # Fails closed to "today's guess still scores for THIS response, just
    # isn't durably recorded" rather than a crash — same contract
    # mark_league_alert_read already documents for a not-yet-migrated table.
    streak_payload = (
        {"current_streak": new_current, "best_streak": new_best}
        if ok
        else _guess_the_player_streak_payload(streak_row)
    )

    return {
        "ok": True,
        "already_answered": False,
        "correct": correct,
        "correct_player": _guess_the_player_correct_identity(pick),
        "streak": streak_payload,
    }


# ---------------------------------------------------------------------------
# "Who is who?" name-match mode — a SECOND, distinct daily mini-game
# (coridian_, 2026-10-19, same Discord thread as the game above): "you get
# two players and one player is, you know, a known name that's good, and
# then one player is kind of an unknown name who maybe has better stats
# than the known name, and so you pick and choose who is who." Unlike the
# game above, BOTH players' real identity is shown up front — what's
# hidden is which of the two real, unlabeled stat lines ("Slot A"/"Slot B")
# belongs to which player. Its own daily pick and its own persisted streak
# (docs/supabase_guess_the_player_name_match.sql) — never mixed with the
# original game's streak, these are different games with different
# difficulty/feel. Selection logic lives in modules.guess_the_player's
# find_name_match_candidates/build_daily_name_match_pick.
# ---------------------------------------------------------------------------

_GUESS_THE_PLAYER_NAME_MATCH_CACHE_TTL_SECONDS = 24 * 60 * 60


def _guess_the_player_name_match_compute_pick(today: str) -> dict[str, Any] | None:
    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        return None
    season_stats = sleeper.get_season_player_stats()
    if not season_stats:
        return None
    return guess_the_player.build_daily_name_match_pick(players_df, season_stats, seed=today)


def _guess_the_player_name_match_daily_pick(today: str) -> dict[str, Any] | None:
    """Today's featured name-match pairing. Same calendar-day boundary as
    _guess_the_player_today (one shared backend, one UTC date for every
    caller) and the same fail-open Redis cache contract as
    _guess_the_player_daily_pick — a separate cache key/namespace so the
    two games' daily picks can never collide or evict each other."""

    cache_key = redis_cache.build_cache_key("guess_the_player_name_match_daily_pick", today)
    try:
        return redis_cache.redis_single_flight_cache(
            cache_key=cache_key,
            ttl_seconds=_GUESS_THE_PLAYER_NAME_MATCH_CACHE_TTL_SECONDS,
            compute=lambda: _guess_the_player_name_match_compute_pick(today),
        )
    except Exception:
        return _guess_the_player_name_match_compute_pick(today)


def _guess_the_player_name_match_identity(pick: dict[str, Any], *, who: str) -> dict[str, Any]:
    return {
        "player_id": pick[f"{who}_player_id"],
        "name": pick[f"{who}_name"],
        "team": pick[f"{who}_team"],
        "position": pick[f"{who}_position"],
        "tier": pick[f"{who}_tier"],
    }


def _guess_the_player_name_match_public_prompt(pick: dict[str, Any]) -> dict[str, Any]:
    """The payload GET actually returns. Both real identities are always
    shown — nothing hidden there — only `slots` keeps the real stat lines
    unlabeled as to which player each belongs to (never alongside
    `famous_slot`/`obscure_slot`, the answer key)."""

    return {
        "pick_id": pick["pick_id"],
        "season": pick["season"],
        "week": pick["week"],
        "famous_player": _guess_the_player_name_match_identity(pick, who="famous"),
        "obscure_player": _guess_the_player_name_match_identity(pick, who="obscure"),
        "slots": {
            slot: {"stat_line": payload["stat_line"], "fantasy_points_ppr": payload["fantasy_points_ppr"]}
            for slot, payload in pick["slots"].items()
        },
    }


def _guess_the_player_name_match_correct_pairing(pick: dict[str, Any]) -> dict[str, Any]:
    return {"famous_slot": pick["famous_slot"], "obscure_slot": pick["obscure_slot"]}


@app.get("/v1/guess-the-player/name-match")
def get_guess_the_player_name_match(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Today's "Who is who?" pairing plus the caller's real, persisted
    streak for THIS game specifically (never the original game's streak).
    League-independent — one shared pairing per calendar day for every
    signed-in user.
    """

    today = _guess_the_player_today()
    pick = _guess_the_player_name_match_daily_pick(today)
    if pick is None:
        return {
            "ok": True,
            "available": False,
            "reason": "no_name_match_pairing_today",
            "prompt": None,
            "already_answered": False,
            "last_result": None,
            "correct_pairing": None,
            "streak": {"current_streak": 0, "best_streak": 0},
        }

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    streak_row, _ = account_store.fetch_guess_the_player_name_match_streak(
        config, str(user.get("_access_token") or ""), user_id=user_id
    )
    already_answered = bool(streak_row) and str(streak_row.get("last_pick_id") or "") == pick["pick_id"]
    last_result = str(streak_row.get("last_result") or "").strip() if already_answered else ""

    return {
        "ok": True,
        "available": True,
        "reason": "",
        "prompt": _guess_the_player_name_match_public_prompt(pick),
        "already_answered": already_answered,
        "last_result": last_result or None,
        # Only revealed once this user has genuinely already answered
        # TODAY's pairing — never alongside an unanswered prompt, which
        # would leak which slot is which before a real guess.
        "correct_pairing": _guess_the_player_name_match_correct_pairing(pick) if already_answered else None,
        "streak": _guess_the_player_streak_payload(streak_row),
    }


class GuessThePlayerNameMatchAnswerRequest(BaseModel):
    pick_id: str
    famous_slot: str


@app.post("/v1/guess-the-player/name-match/answer")
def answer_guess_the_player_name_match(
    body: GuessThePlayerNameMatchAnswerRequest, user: dict[str, Any] = Depends(require_user)
) -> dict[str, Any]:
    """Score one "who is who?" guess against today's real pairing and
    durably update the caller's OWN name-match streak
    (docs/supabase_guess_the_player_name_match.sql) — never the original
    game's streak.

    Idempotent per pick_id, identical contract to answer_guess_the_player:
    resubmitting the SAME day's pick_id replays the already-recorded
    result instead of re-scoring.
    """

    pick_id = str(body.pick_id or "").strip()
    guessed_slot = str(body.famous_slot or "").strip().upper()
    if not pick_id or guessed_slot not in {"A", "B"}:
        raise HTTPException(status_code=422, detail="pick_id and a valid famous_slot ('A' or 'B') are required.")

    today = _guess_the_player_today()
    pick = _guess_the_player_name_match_daily_pick(today)
    if pick is None or pick["pick_id"] != pick_id:
        # The day rolled over (or the cache rotated) between the client's
        # fetch and this submission — fail closed with a reason the client
        # can react to (refetch today's pairing) rather than scoring
        # against stale or mismatched data.
        raise HTTPException(status_code=409, detail="This pick has expired. Refresh and try again.")

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    streak_row, _ = account_store.fetch_guess_the_player_name_match_streak(
        config, access_token, user_id=user_id
    )

    if streak_row and str(streak_row.get("last_pick_id") or "") == pick_id:
        correct = str(streak_row.get("last_result") or "").strip() == "correct"
        return {
            "ok": True,
            "already_answered": True,
            "correct": correct,
            "correct_pairing": _guess_the_player_name_match_correct_pairing(pick),
            "streak": _guess_the_player_streak_payload(streak_row),
        }

    correct = guessed_slot == pick["famous_slot"]
    current_streak = _guess_the_player_streak_int(streak_row, "current_streak")
    best_streak = _guess_the_player_streak_int(streak_row, "best_streak")
    new_current = current_streak + 1 if correct else 0
    new_best = max(best_streak, new_current)

    ok, _ = account_store.upsert_guess_the_player_name_match_streak(
        config,
        access_token,
        {
            "user_id": user_id,
            "current_streak": new_current,
            "best_streak": new_best,
            "last_pick_id": pick_id,
            "last_result": "correct" if correct else "incorrect",
        },
    )
    # Fails closed to "today's guess still scores for THIS response, just
    # isn't durably recorded" rather than a crash — same contract
    # answer_guess_the_player already documents for a not-yet-migrated
    # table.
    streak_payload = (
        {"current_streak": new_current, "best_streak": new_best}
        if ok
        else _guess_the_player_streak_payload(streak_row)
    )

    return {
        "ok": True,
        "already_answered": False,
        "correct": correct,
        "correct_pairing": _guess_the_player_name_match_correct_pairing(pick),
        "streak": streak_payload,
    }


# ---------------------------------------------------------------------------
# League-scoped "Guess the Player" leaderboard — feature-brainstorm audit
# (coridian_, 2026-10-19, "do it all"): both mini-games above already
# persist a real, durable per-user streak; comparing streaks among a
# user's actual leaguemates is pure assembly of that existing data. See
# modules.guess_the_player_leaderboard's module docstring for the full
# "who counts as a leaguemate" + cross-user service-role design (same
# pattern as GET /v1/community/trades above).
# ---------------------------------------------------------------------------


def _guess_the_player_leaderboard_entries(
    config: guess_the_player_leaderboard.LeaderboardConfig,
    *,
    league_id: str,
    table: str,
    members: list[dict[str, Any]],
    user_ids: list[str],
    profiles_by_user: dict[str, dict[str, Any]],
    viewer_user_id: str,
) -> list[dict[str, Any]]:
    streaks_by_user = guess_the_player_leaderboard.fetch_streaks(config, table, user_ids)
    return guess_the_player_leaderboard.build_leaderboard(
        members,
        league_id=league_id,
        streaks_by_user=streaks_by_user,
        profiles_by_user=profiles_by_user,
        viewer_user_id=viewer_user_id,
    )


@app.get("/v1/leagues/{league_id}/guess-the-player/leaderboard")
def get_guess_the_player_leaderboard(
    league_id: str = Depends(require_league_access), user: dict[str, Any] = Depends(require_user)
) -> dict[str, Any]:
    """Both mini-games' real streaks, ranked among the other FantasyDesk
    accounts that have THIS league saved (see modules.guess_the_player_
    leaderboard's module docstring for exactly who that is and isn't).

    Fails closed, same contract as GET /v1/community/trades: any missing
    service-role config, Supabase hiccup, or unexpected error returns an
    empty-but-200 leaderboard rather than a 500 — this is a Dashboard/
    mini-game extra, never something that should block a client.
    """

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    empty_response = {
        "ok": True,
        "configured": False,
        "stat_line": {"entries": []},
        "name_match": {"entries": []},
    }

    try:
        config = guess_the_player_leaderboard.load_leaderboard_config()
        if not config.configured:
            return empty_response

        members = guess_the_player_leaderboard.fetch_league_members(config, league_id)
        if not members:
            return {
                "ok": True,
                "configured": True,
                "stat_line": {"entries": []},
                "name_match": {"entries": []},
            }

        user_ids = [str(member.get("user_id") or "") for member in members]
        profiles_by_user = guess_the_player_leaderboard.fetch_profiles(config, user_ids)
        viewer_user_id = str(user.get("id") or "")

        stat_line_entries = _guess_the_player_leaderboard_entries(
            config,
            league_id=league_id,
            table=guess_the_player_leaderboard.STAT_LINE_STREAKS_TABLE,
            members=members,
            user_ids=user_ids,
            profiles_by_user=profiles_by_user,
            viewer_user_id=viewer_user_id,
        )
        name_match_entries = _guess_the_player_leaderboard_entries(
            config,
            league_id=league_id,
            table=guess_the_player_leaderboard.NAME_MATCH_STREAKS_TABLE,
            members=members,
            user_ids=user_ids,
            profiles_by_user=profiles_by_user,
            viewer_user_id=viewer_user_id,
        )

        return {
            "ok": True,
            "configured": True,
            "stat_line": {"entries": stat_line_entries},
            "name_match": {"entries": name_match_entries},
        }
    except Exception:
        return empty_response


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
    # Both optional and best-effort: only the mobile share flow's RankedPlayer
    # rows carry them (never draft picks — see TradeSharePreviewModal callers,
    # which filter picks out before recording a share). Without a player_id,
    # this asset can never be tracked by the quiet trade-outcome result sweep
    # (modules.trade_outcome_results) — it's simply excluded from that
    # comparison rather than treated as a zero, so legacy shares recorded
    # before this field existed keep working exactly as before.
    player_id: str = ""
    value_score: float | None = None


class RecordTradeShareRequest(BaseModel):
    partner_team_name: str = ""
    send: list[TradeOutcomeAssetSummary] = Field(default_factory=list)
    receive: list[TradeOutcomeAssetSummary] = Field(default_factory=list)
    value_edge_label: str = ""
    # Whichever evaluation lens (Dynasty/Rebuild/Non-Dynasty) was active on
    # screen when this trade was shared — stored so the later result sweep
    # re-values the same players under the SAME lens rather than an
    # arbitrary default, an apples-to-apples comparison. Missing/unknown
    # values fall back to modules.trade_outcome_results.DEFAULT_LENS.
    valuation_lens: str = ""


@app.post("/v1/leagues/{league_id}/trade-outcomes")
def record_trade_share(
    body: RecordTradeShareRequest,
    # NOT resolved -- see resolve_league_path_id's docstring. This records
    # a durable, user-facing history row; resolving the id forward on a
    # write is a bigger risk (silently attributing the record to a
    # different, if more "correct", league) than leaving an occasional
    # stale league_id on a historical record a client explicitly sent.
    league_id: str,
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

    def _asset_dict(asset: TradeOutcomeAssetSummary) -> dict[str, Any]:
        entry: dict[str, Any] = {"name": asset.name.strip()[:80], "position": asset.position.strip()[:8]}
        player_id = asset.player_id.strip()[:64]
        if player_id:
            entry["player_id"] = player_id
        if asset.value_score is not None:
            try:
                entry["value_score"] = float(asset.value_score)
            except (TypeError, ValueError):
                pass
        return entry

    trade_summary = {
        "partner_team_name": body.partner_team_name.strip()[:120],
        "send": [_asset_dict(asset) for asset in body.send[:10]],
        "receive": [_asset_dict(asset) for asset in body.receive[:10]],
        "value_edge_label": body.value_edge_label.strip()[:40],
        "valuation_lens": body.valuation_lens.strip()[:20],
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


class VerdictFeedbackRequest(BaseModel):
    reason: str
    surface: str = "trade_analyzer"
    platform: str = ""
    league_id: str = ""
    lens: str = ""
    strategy: str = ""
    send_ids: list[str] = Field(default_factory=list)
    receive_ids: list[str] = Field(default_factory=list)
    # What the reporter was looking at, echoed so a reviewer can see it.
    verdict_label: str = ""
    confidence: str = ""
    value_delta: float | None = None
    assumptions_line: str = ""


@app.post("/v1/feedback/verdict")
def post_verdict_feedback(
    body: VerdictFeedbackRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Store one "bad verdict" report (modules.verdict_feedback).

    Signed-in only (the response is rate limited like every mutating call),
    but the stored row carries no auth uid: it is inserted as an anonymous
    ``feedback_reports`` row with a one-way account hash in its context, one of
    a fixed set of reasons and no free text. Fails closed (ok: False) rather
    than 500 when the table is not reachable.
    """

    if body.reason not in verdict_feedback.REASONS:
        raise HTTPException(status_code=422, detail="reason must be one of: " + ", ".join(verdict_feedback.REASONS))
    if body.surface not in verdict_feedback.SURFACES:
        raise HTTPException(status_code=422, detail="surface must be one of: " + ", ".join(sorted(verdict_feedback.SURFACES)))
    user_id = str(user.get("id") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}
    row = verdict_feedback.build_feedback_row(
        user_id=user_id,
        reason=body.reason,
        surface=body.surface,
        platform=body.platform,
        league_id=body.league_id,
        lens=body.lens,
        strategy=body.strategy,
        send_ids=body.send_ids,
        receive_ids=body.receive_ids,
        verdict_label=body.verdict_label,
        confidence=body.confidence,
        value_delta=body.value_delta,
        assumptions_line=body.assumptions_line,
    )
    if row is None:
        raise HTTPException(status_code=422, detail="Unrecognised feedback.")
    config = auth_supabase.get_supabase_config()
    # Anonymous insert on purpose (no user bearer): the table's guest policy
    # requires user_id is null, which is what keeps the reporter unidentified.
    headers = auth_supabase.auth_headers(config, "")
    headers["Prefer"] = "return=minimal"
    try:
        response = requests.post(
            auth_supabase.rest_api_url(config, verdict_feedback.FEEDBACK_TABLE),
            headers=headers,
            json=row,
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


def _project_trade_outcome_history(row: dict[str, Any]) -> dict[str, Any]:
    summary = row.get("trade_summary") if isinstance(row.get("trade_summary"), dict) else {}
    result_summary = row.get("result_summary") if isinstance(row.get("result_summary"), dict) else None
    return {
        "id": str(row.get("id") or ""),
        "league_id": str(row.get("league_id") or ""),
        "partner_team_name": str(row.get("partner_team_name") or ""),
        "trade_summary": summary,
        "outcome": str(row.get("outcome") or ""),
        "shared_at": row.get("shared_at"),
        "outcome_recorded_at": row.get("outcome_recorded_at"),
        # Present only once modules.trade_outcome_results's quiet sweep has
        # actually computed something — absent (not a placeholder) the rest
        # of the time, so the mobile Trade History screen only ever renders
        # a result section when there's a real one to show.
        "result_summary": result_summary,
        "result_computed_at": row.get("result_computed_at"),
    }


@app.get("/v1/trade-outcomes/history")
def get_trade_outcome_history(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """This user's answered trades (yes/no/didn't send), newest first, with
    the quiet "did it work out?" result folded in once computed.

    Pull-based only — the mobile Trade History screen (More > Trade
    History) calls this on its own when the user opens it. Nothing calls
    this automatically and nothing here triggers a push or a popup; the
    result itself is computed out-of-band by modules.trade_outcome_results's
    standalone sweep and simply read back here.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": True, "outcomes": []}

    query = (
        f"user_id=eq.{user_id}&outcome=neq.pending"
        "&select=id,league_id,partner_team_name,trade_summary,outcome,shared_at,"
        "outcome_recorded_at,result_summary,result_computed_at"
        "&order=shared_at.desc&limit=50"
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
    return {"ok": True, "outcomes": [_project_trade_outcome_history(row) for row in rows if isinstance(row, dict)]}


# ---------------------------------------------------------------------------
# Community Trade Feed (docs/roadmap.md "Social / community layer") —
# anonymized "craziest trades" feed pulled from ALL users' confirmed,
# high-confidence trade_outcomes rows. See modules/community_trades.py's
# module docstring for the full anonymization/cross-user-read design and
# why this is the one place in this service that uses service-role access
# inside a live request instead of a per-user token.
# ---------------------------------------------------------------------------


@app.get("/v1/community/trades")
def get_community_trades(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Anonymized feed of "interesting" (real, lopsided, high-confidence)
    confirmed trades across every user's real leagues — never the current
    user's own league filter, by design (this IS the cross-league feature).
    Free for every signed-in user, no Premium gate (coridian_'s spec).
    Fails closed to an empty feed on any error, same contract as every
    other Supabase-backed read in this service.
    """

    try:
        config = community_trades.load_community_feed_config()
        if not config.configured:
            return {"ok": True, "trades": [], "reaction_emoji": list(community_trades.COMMUNITY_REACTION_EMOJI)}

        candidates = community_trades.fetch_interesting_trade_outcomes(config)
        opted_out = community_trades.fetch_opted_out_user_ids(config)
        viewer_user_id = str(user.get("id") or "")
        visible = [
            row for row in candidates if str(row.get("user_id") or "") not in opted_out
        ]
        outcome_ids = [str(row.get("id") or "") for row in visible]
        reaction_rows = community_trades.fetch_reaction_rows(config, outcome_ids)
        items = community_trades.build_community_feed_items(
            visible,
            opted_out_user_ids=opted_out,
            reaction_rows=reaction_rows,
            viewer_user_id=viewer_user_id,
        )
        return {"ok": True, "trades": items, "reaction_emoji": list(community_trades.COMMUNITY_REACTION_EMOJI)}
    except Exception:
        return {"ok": True, "trades": [], "reaction_emoji": list(community_trades.COMMUNITY_REACTION_EMOJI)}


class CommunityTradeReactionRequest(BaseModel):
    emoji: str
    action: str = "add"


@app.post("/v1/community/trades/{outcome_id}/react")
def react_to_community_trade(
    outcome_id: str,
    body: CommunityTradeReactionRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Add or remove the caller's own emoji reaction. Uses the caller's own
    access token (never service role) — RLS auth.uid() = user_id on
    community_trade_reactions is sufficient and correct for "my own
    reaction," so this mutation never needs modules.community_trades'
    elevated cross-user access at all.

    outcome_id is an unguessable uuid the caller only ever learns from GET
    /v1/community/trades' own response; this endpoint does not separately
    re-check that the trade is still visible in that feed (e.g. still
    "interesting", or its owner hasn't since opted out) before accepting a
    reaction on it — a deliberately small, documented gap: nothing about a
    reaction (not even its existence) is ever shown back to any client
    except as an anonymous count on an already-anonymized feed item, so a
    stray reaction on a since-hidden trade carries no privacy or identity
    risk, only a harmless uncounted row.
    """

    emoji = body.emoji.strip()
    if emoji not in community_trades.COMMUNITY_REACTION_EMOJI:
        raise HTTPException(
            status_code=422,
            detail="emoji must be one of: " + " ".join(community_trades.COMMUNITY_REACTION_EMOJI),
        )
    action = body.action.strip().lower()
    if action not in {"add", "remove"}:
        raise HTTPException(status_code=422, detail="action must be add or remove.")

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    headers = auth_supabase.auth_headers(config, access_token)
    try:
        if action == "add":
            headers["Prefer"] = "return=minimal,resolution=ignore-duplicates"
            response = requests.post(
                auth_supabase.rest_api_url(config, community_trades.COMMUNITY_REACTIONS_TABLE),
                headers=headers,
                json={"outcome_id": outcome_id, "user_id": user_id, "emoji": emoji},
                timeout=15,
            )
        else:
            query = f"outcome_id=eq.{outcome_id}&user_id=eq.{user_id}&emoji=eq.{emoji}"
            headers["Prefer"] = "return=minimal"
            response = requests.delete(
                auth_supabase.rest_api_url(config, community_trades.COMMUNITY_REACTIONS_TABLE, query),
                headers=headers,
                timeout=15,
            )
    except Exception:
        return {"ok": False, "reason": "not_available"}
    if response.status_code >= 400:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


def _community_preferences_from_settings(settings: dict[str, Any]) -> dict[str, Any]:
    # On by default — absent key means "not opted out", matching
    # coridian_'s "on by default, with a visible opt-out toggle" spec.
    return {"opted_out": bool(settings.get("community_trades_opt_out", False))}


@app.get("/v1/community/preferences")
def get_community_preferences(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """This user's own Community Trade Feed opt-out flag. Backed by the
    existing user_settings table under a "community_trades_opt_out" key —
    same pattern as /v1/push/preferences' "push_categories" key — not a
    new table."""

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    settings, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, **_community_preferences_from_settings({})}
    return {"ok": True, **_community_preferences_from_settings(settings.get("settings") or {})}


class UpdateCommunityPreferencesRequest(BaseModel):
    opted_out: bool


@app.post("/v1/community/preferences")
def update_community_preferences(
    body: UpdateCommunityPreferencesRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Set this user's own Community Trade Feed opt-out flag. When set, this
    user's own confirmed trades must never appear in ANY other user's feed
    — enforced by modules.community_trades.fetch_opted_out_user_ids'
    service-role read, checked on every GET /v1/community/trades, not just
    going forward from the moment this is toggled.
    """

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, **_community_preferences_from_settings({})}
    settings = dict(current.get("settings") or {})
    settings["community_trades_opt_out"] = bool(body.opted_out)
    payload = account_store.build_user_settings_payload(user_id=user_id, settings=settings)
    ok, error = account_store.upsert_user_settings(config, access_token, payload)
    if not ok:
        return {"ok": False, **_community_preferences_from_settings(settings)}
    return {"ok": True, **_community_preferences_from_settings(settings)}


# ---------------------------------------------------------------------------
# Opt-in shared trades (docs/supabase_community_trades.sql). A user explicitly
# shares a Trade Analyzer result; everything runs on the caller's own token
# (RLS), never service role. Missing table -> {"available": false}.
# ---------------------------------------------------------------------------

_SHARED_TRADE_ID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


def _shared_trade_id_or_422(trade_id: str) -> str:
    if not _SHARED_TRADE_ID_RE.match(trade_id or ""):
        raise HTTPException(status_code=422, detail="Invalid trade id.")
    return trade_id


@app.get("/v1/community/shared-trades")
def list_shared_community_trades(
    limit: int = 30, user: dict[str, Any] = Depends(require_user)
) -> dict[str, Any]:
    """Feed of opted-in shared trades. available=false when storage is not
    set up (or unreachable): clients hide the feed and the share toggle."""

    config = auth_supabase.get_supabase_config()
    if not auth_supabase.is_configured(config):
        return {"ok": True, "available": False, "trades": []}
    try:
        trades = community_shared_trades.fetch_feed(
            config, str(user.get("_access_token") or ""), str(user.get("id") or ""), limit
        )
    except community_shared_trades.Unavailable:
        return {"ok": True, "available": False, "trades": []}
    return {"ok": True, "available": True, "trades": trades}


class ShareCommunityTradeRequest(BaseModel):
    send: list[dict[str, Any]] = Field(default_factory=list, max_length=community_shared_trades.ASSET_MAX)
    receive: list[dict[str, Any]] = Field(default_factory=list, max_length=community_shared_trades.ASSET_MAX)
    grade: str = Field(default="", max_length=24)
    band: str = Field(default="", max_length=64)
    why: str = Field(default="", max_length=1000)
    display_name: str = Field(default="", max_length=100)


@app.post("/v1/community/shared-trades")
def share_community_trade(
    body: ShareCommunityTradeRequest, user: dict[str, Any] = Depends(require_user)
) -> dict[str, Any]:
    user_id = str(user.get("id") or "")
    token = str(user.get("_access_token") or "")
    config = auth_supabase.get_supabase_config()
    if not user_id or not auth_supabase.is_configured(config):
        return {"ok": False, "available": False, "reason": "not_available"}
    try:
        row = community_shared_trades.build_share_row(user_id, body.model_dump())
    except community_shared_trades.ShareError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    try:
        recent = community_shared_trades.count_recent_shares(config, token, user_id)
        if recent >= community_shared_trades.SHARES_PER_HOUR:
            raise HTTPException(status_code=429, detail="You're sharing too fast. Try again later.")
        trade = community_shared_trades.insert_share(config, token, row, user_id)
    except community_shared_trades.Unavailable:
        return {"ok": False, "available": False, "reason": "not_available"}
    return {"ok": True, "available": True, "trade": trade}


@app.delete("/v1/community/shared-trades/{trade_id}")
def delete_shared_community_trade(trade_id: str, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    trade_id = _shared_trade_id_or_422(trade_id)
    config = auth_supabase.get_supabase_config()
    try:
        community_shared_trades.delete_share(
            config, str(user.get("_access_token") or ""), trade_id, str(user.get("id") or "")
        )
    except community_shared_trades.Unavailable:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True}


class ReportSharedTradeRequest(BaseModel):
    reason: str = Field(default="", max_length=200)


@app.post("/v1/community/shared-trades/{trade_id}/report")
def report_shared_community_trade(
    trade_id: str, body: ReportSharedTradeRequest, user: dict[str, Any] = Depends(require_user)
) -> dict[str, Any]:
    """Store a report (one per user per trade). The database trigger hides the
    trade once it reaches community_shared_trades.HIDE_AFTER_REPORTS."""

    trade_id = _shared_trade_id_or_422(trade_id)
    config = auth_supabase.get_supabase_config()
    try:
        community_shared_trades.insert_report(
            config, str(user.get("_access_token") or ""), trade_id, str(user.get("id") or ""), body.reason
        )
    except community_shared_trades.Unavailable:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True}


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

    market_rating/opportunity_rating/scarcity_rating/role_rating/
    durability_rating are the Model tab's sub-rating chip row — the same
    four composite-score inputs above (plus a durability read), re-expressed
    on the 0-99 OVR-ring scale instead of their raw composite units, via
    modules.player_quick_view.sub_ratings. Kept alongside the raw
    *_score fields rather than replacing them: those stay the source of
    truth for decision_fit_narrative and any other raw-unit consumer.
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
        "depth_chart_note": _project_depth_chart_note(row),
        "decision_fit_narrative": player_quick_view.decision_fit_narrative(players_df, row),
        **{
            key: _clean_json_value(value)
            for key, value in player_quick_view.sub_ratings(players_df, row).items()
        },
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
        # Not in the valued frame (no FantasyCalc row, filtered out, ...):
        # identity still resolves from Sleeper's directory so the client
        # never has to render "FA" for a player Sleeper lists on a team.
        return {
            "ok": True,
            "stats": None,
            "bio": None,
            "model": None,
            "identity": _quick_view_identity(player_id, None),
            "reason": "not_found",
        }

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
        "identity": _quick_view_identity(player_id, row),
        "reason": "",
    }


@app.get("/v1/players/{player_id}/percentile-explorer")
def get_player_percentile_explorer(
    player_id: str,
    stat: str,
    pool: str = "position",
    season: int | None = None,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Distribution + nearby real players behind one quick-view stat tile.

    Same pool/percentile primitive as the tiles (modules.percentile_explorer),
    and gated exactly like quick-view: any signed-in user, because the tile
    percentiles themselves are not Pro-gated. Only the loaded season exists, so
    a different `season` returns reason "season_unavailable".
    """

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    matches = players_df[players_df["player_id"] == player_id]
    if matches.empty:
        return {"ok": True, "stat": stat, "pool": pool, "reason": "no_data", "scopes": ["season"]}
    payload = percentile_explorer.build_explorer(players_df, matches.iloc[0], stat=stat, pool=pool)
    if season is not None and payload.get("season") not in (None, season):
        return {**payload, "ok": True, "reason": "season_unavailable", "bins": [], "nearby": [], "player": None}
    return _clean_json_value({"ok": True, **payload})


def _quick_view_bye(team: str | None, *, today: date | None = None) -> tuple[int | None, bool]:
    """(bye week, is it this NFL week) from the real nflverse schedule.

    No team (free agent) or no schedule -> (None, False); never invented.
    Jan-Feb belongs to the finished season, so it reports no bye. The
    "this week" flag is only ever True in season (trade_grade's calendar
    week is 0 in the offseason).
    """

    if not team:
        return None, False
    today = today or datetime.now(timezone.utc).date()
    if today.month < 3:
        return None, False
    try:
        bye = nfl_schedule.team_bye_week(team, today.year)
    except Exception:
        return None, False
    if bye is None:
        return None, False
    return bye, trade_grade.estimate_nfl_week(today) == bye


def _quick_view_identity(player_id: str, row: pd.Series | None) -> dict[str, Any]:
    """Identity (name/team/position/age) plus an honest value read for the
    quick view. Team/position/age come from the valued row when present and
    otherwise from Sleeper's directory, so a player Sleeper lists on a team
    is never "FA" just because our valuation (e.g. a FantasyCalc row) is
    missing. ``value_note`` explains an absent value instead of a bare dash.
    """

    def _blank(value: Any) -> bool:
        if value is None:
            return True
        try:
            if pd.isna(value):
                return True
        except (TypeError, ValueError):
            pass
        return not str(value).strip()

    def _from_row(key: str) -> Any:
        if row is None or key not in row.index:
            return None
        value = row.get(key)
        return None if _blank(value) else value

    directory: dict[str, Any] = {}
    try:
        raw = (sleeper.get_players() or {}).get(str(player_id))
        if isinstance(raw, dict):
            directory = raw
    except Exception:
        directory = {}

    name = _from_row("name") or directory.get("full_name") or " ".join(
        str(part) for part in (directory.get("first_name"), directory.get("last_name")) if part
    )
    team = _from_row("team") or directory.get("team") or None
    position = _from_row("position") or directory.get("position") or None
    age: int | None = None
    raw_age = _from_row("age")
    if raw_age is not None:
        try:
            parsed = float(raw_age)
            if 0 < parsed < 99:
                age = int(parsed)
        except (TypeError, ValueError):
            age = None
    if age is None:
        raw_dir_age = directory.get("age")
        if isinstance(raw_dir_age, (int, float)) and 0 < raw_dir_age < 99:
            age = int(raw_dir_age)
        else:
            birth = str(directory.get("birth_date") or "").strip()[:10]
            try:
                born = datetime.strptime(birth, "%Y-%m-%d")
                age = int((datetime.now() - born).days // 365.25)
            except ValueError:
                age = None

    value = _clean_json_value(_from_row("value_score"))
    if isinstance(value, (int, float)) and value <= 0:
        value = None
    bye_week, on_bye_this_week = _quick_view_bye(str(team) if team else None)
    return {
        "bye_week": bye_week,
        "on_bye_this_week": on_bye_this_week,
        "player_id": str(player_id),
        "name": str(name or ""),
        "team": str(team) if team else None,
        "position": str(position) if position else None,
        "age": age,
        "status": str(_from_row("status") or directory.get("status") or "") or None,
        "value_score": value,
        "overall_rating": _clean_json_value(_from_row("overall_rating")),
        "value_note": "" if value is not None else "No market value yet",
    }


MAX_WEEKLY_STATS_SEASONS_BACK = 7


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


def _projection_summary_dict(result: dict[str, Any]) -> dict[str, Any]:
    """Trim `modules.player_projections.project_player_week`'s output to the
    fields a mobile client needs to render an honest per-game projection.

    `status` drives the client's rendering: anything other than `"ok"` means
    "no projection" (e.g. "No projection yet" / "Bye week") — the numeric
    fields are always `None` for a non-"ok" status so a client can never
    accidentally render a stale/fabricated number by skipping the status
    check. Deliberately omits `basis` (recency-weighted internals) — that's
    diagnostic detail this first pass doesn't need to ship to a client.
    """

    status = str(result.get("status") or "unknown_player")
    summary: dict[str, Any] = {
        "status": status,
        "point_estimate": None,
        "low": None,
        "high": None,
        "confidence": None,
        "opponent": result.get("opponent"),
    }
    if status == "ok":
        summary.update(
            {
                "point_estimate": result.get("point_estimate"),
                "low": result.get("low"),
                "high": result.get("high"),
                "confidence": result.get("confidence"),
            }
        )
    return summary


def _weekly_projection_for_player(
    player_id: str,
    week: int,
    season: int,
    *,
    players_lookup: dict[str, Any],
    weekly_stats: dict[str, Any],
    defense_strength: dict[str, Any],
    team_qb_pass_attempts_by_team: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One player's per-game projection for one week, from data already
    fetched once by the caller (never re-reads the season stats cache file
    or recomputes defense strength per player/week — see the callers below).

    `team_qb_pass_attempts_by_team` is likewise built once by the caller
    (`player_projections.team_qb_pass_attempts_by_week`) and forwarded so
    `project_player_week`'s `team_qb_situation_changed_recently` basis flag
    never re-scans the whole `players_lookup` per call — see that
    function's own docstring.
    """

    record = weekly_stats.get(str(player_id))
    weekly_rows = record.get("weekly") if isinstance(record, dict) else None
    result = player_projections.project_player_week(
        player_id,
        week,
        season,
        players=players_lookup,
        player_weekly_rows=weekly_rows or [],
        defense_strength=defense_strength,
        team_qb_pass_attempts_by_team=team_qb_pass_attempts_by_team,
    )
    return _projection_summary_dict(result)


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

    Each not-yet-played, non-bye week additionally carries a `projection`
    (modules.player_projections.project_player_week — point estimate, low/
    high band, confidence, honest edge-case status; see
    `_projection_summary_dict`). Already-played weeks and byes carry
    `projection: null` — that information is either already on the row
    (the final score) or moot (bye), so this never draws two competing
    numbers on one row. This is an ADDITIVE field: existing consumers of
    this endpoint that don't know about `projection` are unaffected.
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

    # Per-game projection for the remaining (not-yet-played, non-bye)
    # schedule. Only fetched/computed at all when at least one such week
    # exists — a fully-played or bye-only schedule (e.g. a look-back at a
    # finished season) never touches the projection data sources. When it
    # does run, players lookup / season weekly stats / opponent-defense
    # signal are each fetched ONCE for the whole request, not once per week
    # — see `_weekly_projection_for_player`'s own docstring for why that
    # matters.
    projectable_weeks = [week for week in weeks if not week.get("bye") and not week.get("played")]
    if not projectable_weeks:
        for week in weeks:
            week["projection"] = None
    else:
        try:
            players_lookup = sleeper.get_players()
            weekly_stats = sleeper.get_season_player_stats(season=season, retain_weekly=True)
            projection_defense_strength = player_projections.team_defense_points_allowed_by_position(
                season, weekly_stats=weekly_stats, players=players_lookup
            )
            # Built ONCE for the whole request, same reason as
            # players_lookup/weekly_stats/projection_defense_strength above
            # — see team_qb_pass_attempts_by_week's own docstring: this
            # player's team doesn't change across the up-to-18-week loop
            # below, so the expensive players_lookup scan it replaces would
            # otherwise redo the same work once per remaining week.
            team_qb_pass_attempts = player_projections.team_qb_pass_attempts_by_week(
                players_lookup, weekly_stats
            )
            for week in weeks:
                if week.get("bye") or week.get("played"):
                    week["projection"] = None
                    continue
                week["projection"] = _weekly_projection_for_player(
                    player_id,
                    int(week["week"]),
                    season,
                    players_lookup=players_lookup,
                    weekly_stats=weekly_stats,
                    defense_strength=projection_defense_strength,
                    team_qb_pass_attempts_by_team=team_qb_pass_attempts,
                )
        except Exception:
            # Best-effort enrichment, same "fails soft" contract as every
            # other enrichment fetch in this file — a transient issue
            # loading player-stats/defense data must never break the real
            # schedule data already built above.
            for week in weeks:
                week.setdefault("projection", None)

    return {"ok": True, "team": str(team), "season": season, "weeks": weeks}


# ---------------------------------------------------------------------------
# External (bot) read-only projections API — Phase 1 of coridian_'s external
# content-posting bot wish list (full contract: docs/external-api-contract.md).
# That bot has no Supabase user account, so it cannot use `require_user`; it
# authenticates with a single static API key instead, checked separately
# from — and never granting access to — any `require_user`-gated route
# above. This is the ONLY place that key is checked.
# ---------------------------------------------------------------------------

EXTERNAL_API_KEY_ENV = "FANTASYDESK_EXTERNAL_API_KEY"

# Bumped only when modules.player_projections.project_player_week's actual
# FORMULA changes in a way that would shift point_estimate/low/high/
# confidence for the same (player_id, week, season) inputs. A response
# *field* change (adding/renaming/removing a key) is a separate, breaking-
# vs-non-breaking concern this constant does not track — see
# docs/external-api-contract.md's versioning policy for both.
EXTERNAL_PROJECTIONS_MODEL_VERSION = "v1"

# Sleeper's own player_id already *is* this app's canonical player id (see
# modules.player_identity.SUPPORTED_DIRECT_PLATFORMS) — this is reported so
# a caller never has to guess which id space `player_id` lives in.
EXTERNAL_ID_NAMESPACE = "sleeper"

# nfl_schedule.team_schedule only ever returns regular-season games (its own
# docstring: "Playoff rounds (game_type != 'REG') are excluded"), so every
# week this API can project is always a regular-season week today. A real
# constant (not a guess) — if postseason projections are ever added, this is
# where that would stop being a hardcoded value.
EXTERNAL_PROJECTIONS_SEASON_TYPE = "regular"

# Max number of player ids surfaced inline in `completeness.*_player_ids` —
# this is diagnostic detail for a human/bot debugging a gap, not meant to
# re-list the whole slate; `*_player_id_count` always reports the real total
# regardless of how many ids are actually included.
EXTERNAL_COMPLETENESS_ID_SAMPLE_LIMIT = 25

# Phase 4 of coridian_'s wish list (docs/external-api-contract.md):
# lineup-popularity ("started_percent") evidence is genuinely useful to a
# posting bot deciding whether a "sit" post is even meaningful, but no
# licensed or otherwise available started-percent data source is wired into
# this codebase today — FantasyDesk's own roster data is ROSTERED percent,
# which Phase 4's own spec explicitly warns is NOT the same claim as STARTED
# percent. Per the same honesty discipline as every other `status`/`null`
# field in this contract, this is a real, present, well-documented field
# that is correctly unavailable rather than a fabricated or substituted
# number. A fresh dict is returned per call so no caller can mutate the
# shared default.
def _external_lineup_popularity_unavailable() -> dict[str, Any]:
    return {
        "available": False,
        "unavailable_reason": (
            "No licensed or otherwise available lineup-popularity/start-rate "
            "data source is integrated in this codebase. FantasyDesk's own "
            "roster-ownership data reflects ROSTERED percent, not STARTED "
            "percent, and is deliberately never substituted here — see "
            "docs/external-api-contract.md."
        ),
        "started_percent": None,
        "platform": None,
        "league_format": None,
        "scoring_format": None,
        "observed_at": None,
        "source_url": None,
        "population": None,
    }


def _external_position_group(position: str | None) -> str | None:
    """`"skill"` (QB/RB/WR/TE) / `"kicker"` (K) / `"unsupported"` (anything
    else, e.g. DEF/IDP) / `None` when no position is known at all (e.g. an
    unknown player id). Lets a bot tell a kicker apart from a skill-position
    player without hardcoding its own position list — see
    `player_projections.OFFENSIVE_POSITIONS`/`KICKER_POSITION`, the same
    sets this endpoint's own completeness accounting uses below."""

    if not position:
        return None
    normalized = str(position).strip().upper()
    if normalized in player_projections.OFFENSIVE_POSITIONS:
        return "skill"
    if normalized == player_projections.KICKER_POSITION:
        return "kicker"
    return "unsupported"


def _external_availability(result: dict[str, Any], *, checked_at: str) -> dict[str, Any]:
    """Item 5 of coridian_'s wish list: a typed official status, kept
    strictly separate from the model's own `status` field above (never
    conflated with "bye_week"/"insufficient_player_data"/etc.). `injury_status`
    is Sleeper's own typed field (e.g. "Questionable"/"Out"/"IR"/"Sus") —
    official in the sense of being the structured status every other screen
    in this app already reads, but it carries no article URL of its own, so
    `official_status_source_url` is honestly `None` rather than a fabricated
    link: a caller that wants sourced, timestamped news evidence (with real
    `source_urls`) should call `GET /v1/external/players/{player_id}/news`
    (Phase 2) instead — this field is never a substitute for that endpoint.
    `game_status` reuses this same payload's own schedule fields (never a
    second, independently-derived live-game signal) — "bye" when there's no
    game, "completed_or_in_progress" once kickoff has passed or nflverse has
    a final score (the same two-state honesty `nfl_schedule.game_has_started`
    already uses elsewhere — this app has no live in-game feed, so
    "in_progress" and "final" are never distinguished), "upcoming" when a
    real kickoff is known and hasn't passed, "unknown" only when none of the
    above could be determined (e.g. `no_schedule_data`).
    """

    injury_status = result.get("injury_status")
    if result.get("bye"):
        game_status = "bye"
    elif result.get("played") is True:
        game_status = "completed_or_in_progress"
    elif result.get("kickoff_at"):
        game_status = "upcoming"
    else:
        game_status = "unknown"
    return {
        "official_status": injury_status,
        "official_status_source": "sleeper_player_directory" if injury_status else None,
        "official_status_source_url": None,
        "checked_at": checked_at,
        "game_status": game_status,
    }


def _external_factors(result: dict[str, Any], *, as_of: str) -> list[dict[str, Any]] | None:
    """Item 3 of coridian_'s wish list: structured explanation factors,
    supplied only when a real, already-computed input actually backs them —
    every value here is read straight off `project_player_week`'s own
    `basis` dict (never a generated narrative, never fabricated when a
    signal has no real sample). `None` (not `[]`) for any non-`"ok"` status,
    since `basis` itself only exists when a real projection was produced.
    """

    if result.get("status") != "ok":
        return None
    basis = result.get("basis") or {}
    factors: list[dict[str, Any]] = []
    if basis.get("recent_games_played"):
        weeks_used = basis.get("recent_weeks_used")
        factors.append(
            {
                "code": "recent_scoring_trend",
                "observed_value": basis.get("recent_weighted_avg_ppr"),
                "comparison_baseline": None,
                "unit": "fantasy_points_ppr_per_game",
                "period": f"last {weeks_used} played week(s)" if weeks_used else "recent played weeks",
                "source": "fantasygmlab_weekly_stats",
                "as_of": as_of,
            }
        )
    # Only when there's a REAL (non-neutral-fallback) opponent-defense
    # signal — opponent_defense_has_signal is False whenever the opponent
    # has too small a sample, and the multiplier is a neutral 1.0 in that
    # case; surfacing that as a "factor" would misrepresent a non-finding as
    # a finding.
    # v2: a signal only counts as a factor when it actually moved the number.
    if basis.get("opponent_defense_has_signal") and basis.get("opponent_multiplier_applied", True):
        factors.append(
            {
                "code": "opponent_defense_strength",
                "observed_value": basis.get("opponent_multiplier"),
                "comparison_baseline": 1.0,
                "unit": "multiplier_vs_league_average_points_allowed",
                "period": f"last {basis.get('opponent_defense_games_sampled')} sampled game(s)",
                "source": "nflverse_points_allowed_by_position",
                "as_of": as_of,
            }
        )
    if basis.get("team_qb_quality_has_signal") and basis.get("team_qb_quality_multiplier_applied", True):
        factors.append(
            {
                "code": "team_starting_qb_quality",
                "observed_value": basis.get("team_qb_quality_score"),
                "comparison_baseline": None,
                "unit": "team_qb_quality_score",
                "period": "season to date",
                "source": "fantasygmlab_team_qb_quality_model",
                "as_of": as_of,
            }
        )
    if basis.get("usage_implied_ppr") is not None:
        factors.append(
            {
                "code": "usage_implied_scoring",
                "observed_value": basis.get("usage_implied_ppr"),
                "comparison_baseline": basis.get("season_avg_ppr"),
                "unit": "fantasy_points_ppr_per_game",
                "period": f"{basis.get('season_games_played')} played game(s) this season",
                "source": "fantasygmlab_weekly_stats",
                "as_of": as_of,
            }
        )
    availability = basis.get("availability") or {}
    if availability.get("applied"):
        factors.append(
            {
                "code": "availability",
                "observed_value": availability.get("multiplier"),
                "comparison_baseline": 1.0,
                "unit": "multiplier_on_projection",
                "period": str(availability.get("reason") or ""),
                "source": "sleeper_injury_status",
                "as_of": as_of,
            }
        )
    return factors


def require_external_api_key(authorization: str | None = Header(default=None)) -> None:
    """Static bearer-token auth for `/v1/external/*` — a single shared
    secret (`FANTASYDESK_EXTERNAL_API_KEY`, see docs/external-api-contract.md),
    not a per-user Supabase session: there is no "user" for a bot. Uses
    `secrets.compare_digest` (never `==`) so comparison time doesn't leak how
    much of the key was right, and raises the identical 401 regardless of
    *why* the key was rejected (missing header, wrong scheme, wrong key) —
    a caller can never learn it was "close."
    """

    expected = app_config.config_value(EXTERNAL_API_KEY_ENV)
    if not expected:
        raise HTTPException(status_code=503, detail="External API is not configured.")
    scheme, _, token = (authorization or "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _external_projection_payload(
    player_id: str, season: int, week: int, result: dict[str, Any]
) -> dict[str, Any]:
    """Shape one `project_player_week` result into the external contract
    (docs/external-api-contract.md): `player_id`/`season`/`week`/
    `scoring_format`/`calculated_at`/`model_version` are always present;
    `projected_points`/`low`/`high`/`confidence` are `None` for any non-"ok"
    status — the same honesty discipline as `_projection_summary_dict`
    above (never fabricate a number for a bye week, unknown player, etc.).
    `scoring_format` is always `"ppr"`: `project_player_week` only ever
    computes PPR points — there is no multi-format support to report here.

    Everything below `model_version` is additive (docs/external-api-
    contract.md's own versioning policy: new fields are always safe) and
    resolved straight from `project_player_week`'s own result dict — see
    `modules.player_projections._player_identity_fields` and the schedule
    context (`is_home`/`game_id`/`kickoff_at`/`bye`/`played`) that function
    now threads through every status branch. No second fetch, no identity
    guessing by name: this is the same canonical `players` row
    `project_player_week` already resolved.
    """

    status = str(result.get("status") or "unknown_player")
    position = result.get("position")
    calculated_at = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "player_id": str(player_id),
        "id_namespace": EXTERNAL_ID_NAMESPACE,
        "season": int(season),
        "week": int(week),
        "scoring_format": "ppr",
        "status": status,
        "projected_points": None,
        "low": None,
        "high": None,
        "confidence": None,
        "calculated_at": calculated_at,
        "model_version": EXTERNAL_PROJECTIONS_MODEL_VERSION,
        # Identity (item 1): resolved from the same canonical players row
        # project_player_week already has in hand — never guessed by name.
        "display_name": result.get("display_name"),
        "team": result.get("team"),
        "position": position,
        "position_group": _external_position_group(position),
        "active": result.get("active"),
        # Game/schedule context (item 1): explicit null for no-game/bye
        # rather than a fabricated opponent — see modules.nfl_schedule.
        "opponent": result.get("opponent"),
        "is_home": result.get("is_home"),
        "bye": result.get("bye"),
        "game_id": result.get("game_id"),
        "kickoff_at": result.get("kickoff_at"),
        # Availability (item 5) and structured factors (item 3) — see their
        # own docstrings for the honesty discipline each follows.
        "availability": _external_availability(result, checked_at=calculated_at),
        "factors": _external_factors(result, as_of=calculated_at),
        # Lineup-popularity evidence (item 4) — correctly unavailable today;
        # see `_external_lineup_popularity_unavailable`'s own docstring.
        "lineup_popularity": _external_lineup_popularity_unavailable(),
    }
    if status == "ok":
        payload.update(
            {
                "projected_points": result.get("point_estimate"),
                "low": result.get("low"),
                "high": result.get("high"),
                "confidence": result.get("confidence"),
            }
        )
    return payload


@app.get(
    "/v1/external/players/{player_id}/projections",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_player_projection(
    player_id: str,
    week: int,
    season: int | None = None,
) -> dict[str, Any]:
    """One player's weekly projection, for the external content-posting bot
    (Phase 1 of coridian_'s wish list — docs/external-api-contract.md).
    Always 200 with a `status` field; edge cases (bye week, unknown player,
    unsupported position, etc.) pass through honestly with every numeric
    field null, never an HTTP error — mirrors `/v1/players/{id}/schedule`'s
    own `_projection_summary_dict` discipline above.
    """

    resolved_season = int(season) if season is not None else sleeper.default_player_stats_season()
    result = player_projections.project_player_week(str(player_id), int(week), resolved_season)
    return _external_projection_payload(player_id, resolved_season, int(week), result)


@app.get(
    "/v1/external/projections",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_week_projections(
    week: int,
    season: int | None = None,
    position: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    """This week's full projectable slate (QB/RB/WR/TE/K), in one call — a
    posting bot deciding what to post about almost always wants "this
    week's slate", not one player id at a time (see
    docs/external-api-contract.md). Shared inputs (players lookup, season
    weekly stats, opponent-defense signal) are fetched once for the whole
    request, the same pattern `/v1/players/{id}/schedule` already uses via
    `_weekly_projection_for_player` above. Optional `position` filters to
    one of QB/RB/WR/TE/K.

    `limit`/`offset` (item 2) are purely additive and backward-compatible:
    omitted, every item is returned exactly as before. `completeness` and
    `covered_game_ids` are always computed over the FULL slate (before any
    pagination slice) — a paginated page is never itself evidence of
    completeness, and completeness metadata must never look different
    just because a caller happened to page through the response.
    """

    resolved_season = int(season) if season is not None else sleeper.default_player_stats_season()
    position_filter = str(position).strip().upper() if position else None
    if position_filter and position_filter not in player_projections.PROJECTABLE_POSITIONS:
        raise HTTPException(status_code=422, detail="position must be one of QB, RB, WR, TE, K.")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0.")
    if limit is not None and limit < 1:
        raise HTTPException(status_code=422, detail="limit must be >= 1.")

    generated_at = datetime.now(timezone.utc).isoformat()
    players = sleeper.get_players()
    weekly_stats = sleeper.get_season_player_stats(season=resolved_season, retain_weekly=True)
    defense_strength = player_projections.team_defense_points_allowed_by_position(
        resolved_season, weekly_stats=weekly_stats, players=players
    )
    # Built ONCE for the whole request, same reason as players/weekly_stats/
    # defense_strength above — coridian_'s performance audit, 2026-10-19:
    # this endpoint can project hundreds of WR/TEs in one call (the full
    # league-wide slate), and each one used to make
    # project_player_week redo this same ~11k-entry `players` scan from
    # scratch via _team_starting_qb_changed_recently. See
    # team_qb_pass_attempts_by_week's own docstring.
    team_qb_pass_attempts = player_projections.team_qb_pass_attempts_by_week(players, weekly_stats)

    # Completeness accounting (item 2) — see docs/external-api-contract.md
    # for the exact, precise definition this implements. The "candidate"
    # universe is deliberately narrowed to real, team-affiliated players at
    # a projectable position: a free agent/retired player at e.g. WR is a
    # real Sleeper row but was never a real lineup candidate this week, so
    # counting it as "missing" would make completeness meaningless (this is
    # the root cause behind the bug report that prompted this change — see
    # the contract's own change history entry for this version).
    skill_candidate_total = 0
    skill_resolved_total = 0
    kicker_candidate_total = 0
    kicker_resolved_total = 0
    unresolved_player_ids: list[str] = []
    no_schedule_data_player_ids: list[str] = []
    covered_game_ids: set[str] = set()

    items: list[dict[str, Any]] = []
    for player_id, player in players.items():
        player_position = str((player or {}).get("position") or "").strip().upper()
        if player_position not in player_projections.PROJECTABLE_POSITIONS:
            continue
        if position_filter and player_position != position_filter:
            continue
        record = weekly_stats.get(str(player_id))
        weekly_rows = record.get("weekly") if isinstance(record, dict) else None
        result = player_projections.project_player_week(
            player_id,
            int(week),
            resolved_season,
            players=players,
            player_weekly_rows=weekly_rows or [],
            defense_strength=defense_strength,
            team_qb_pass_attempts_by_team=team_qb_pass_attempts,
        )
        payload = _external_projection_payload(player_id, resolved_season, int(week), result)
        items.append(payload)

        is_skill = player_position in player_projections.OFFENSIVE_POSITIONS
        has_team = bool((player or {}).get("team"))
        if has_team:
            identity_resolved = bool(payload.get("display_name")) and bool(payload.get("team"))
            if identity_resolved:
                if is_skill:
                    skill_resolved_total += 1
                else:
                    kicker_resolved_total += 1
            else:
                unresolved_player_ids.append(str(player_id))
            if is_skill:
                skill_candidate_total += 1
            else:
                kicker_candidate_total += 1
            if payload.get("status") == "no_schedule_data":
                no_schedule_data_player_ids.append(str(player_id))
        if payload.get("game_id"):
            covered_game_ids.add(str(payload["game_id"]))

    total_items = len(items)
    page = items[offset : offset + limit] if limit is not None else (items[offset:] if offset else items)

    # Vacuously true (0 == 0) when the requested position_scope excludes
    # that bucket entirely (e.g. position=K never has any skill candidates)
    # — "complete" is always judged only within what was actually requested.
    skill_complete = skill_candidate_total == skill_resolved_total
    kicker_complete = kicker_candidate_total == kicker_resolved_total

    return {
        "season": resolved_season,
        "week": int(week),
        "season_type": EXTERNAL_PROJECTIONS_SEASON_TYPE,
        "scoring_format": "ppr",
        "model_version": EXTERNAL_PROJECTIONS_MODEL_VERSION,
        "generated_at": generated_at,
        "source": {
            "players": "sleeper_player_directory",
            "schedule": "nflverse_games_csv",
            "weekly_stats": "sleeper_weekly_stats",
            "as_of": generated_at,
        },
        "position_scope": [position_filter] if position_filter else list(player_projections.PROJECTABLE_POSITIONS),
        "pagination": {
            "offset": offset,
            "limit": limit,
            "returned": len(page),
            "total": total_items,
            "has_more": (offset + len(page)) < total_items,
        },
        "completeness": {
            "skill_position_candidate_total": skill_candidate_total,
            "skill_position_resolved_total": skill_resolved_total,
            "skill_position_complete": skill_complete,
            "kicker_candidate_total": kicker_candidate_total,
            "kicker_resolved_total": kicker_resolved_total,
            "kicker_complete": kicker_complete,
            "unresolved_player_ids": unresolved_player_ids[:EXTERNAL_COMPLETENESS_ID_SAMPLE_LIMIT],
            "unresolved_player_id_count": len(unresolved_player_ids),
            "no_schedule_data_player_ids": no_schedule_data_player_ids[:EXTERNAL_COMPLETENESS_ID_SAMPLE_LIMIT],
            "no_schedule_data_player_id_count": len(no_schedule_data_player_ids),
            # True only when every real, team-affiliated candidate in the
            # requested position_scope resolved a canonical identity AND
            # had real schedule data this week — never inferred from "got a
            # 200" or "no pagination was requested" (see this function's
            # own docstring and docs/external-api-contract.md).
            "complete": skill_complete and kicker_complete and not no_schedule_data_player_ids,
        },
        "covered_game_ids": sorted(covered_game_ids),
        "items": page,
    }


# ---------------------------------------------------------------------------
# External (bot) structured news evidence — Phase 2 of coridian_'s external
# content-posting bot wish list (full contract: docs/external-api-contract.md).
# Gated by the exact same require_external_api_key dependency as Phase 1
# above; this section adds no new auth.
# ---------------------------------------------------------------------------


def _external_news_players_frame() -> Any:
    """Players table for the external news routes, opened read-only.

    Deliberately NOT ``rankings.load_players`` / ``build_players_table``,
    which can write back to the real ``data/players.db`` from inside a
    request. An empty frame means "players table unavailable" and callers
    degrade honestly.
    """

    return news_identity.read_players_frame(PLAYERS_DB_PATH)


def _external_news_payload(
    player_id: str,
    group: Mapping[str, Any],
    *,
    superseded_by: str,
    checked_at: str,
    identity: Mapping[str, Any] | None = None,
    now_ts: int | None = None,
) -> dict[str, Any]:
    """Shape one modules.news_intelligence.group_player_events_by_identity
    group into the external contract (docs/external-api-contract.md):
    `published_at` is the group's earliest-known article timestamp (first
    report), honestly `None` when no member article carries one; `checked_at`
    is this response's own computation time (nothing here is persisted with
    a separate "last verified" timestamp to report instead) — the same
    honesty discipline the Phase 1 projections payload's `calculated_at`
    already uses.
    """

    event: news_intelligence.FootballEvent = group["event"]
    published_at = (
        datetime.fromtimestamp(event.article_time, tz=timezone.utc).isoformat()
        if event.article_time and event.article_time > 0
        else None
    )
    # Additive source-backed contract fields (modules/external_news_contract.py).
    contract = (
        external_news_contract.build_contract_fields(
            group=group,
            identity=identity,
            superseded_by=superseded_by,
            now_ts=now_ts if now_ts is not None else int(time.time()),
        )
        if identity is not None
        else {}
    )
    return {
        **contract,
        "player_id": str(player_id),
        "event_identity": event.event_identity,
        "event_type": event.event_type,
        "description": event.explanation,
        "source_urls": list(group.get("source_urls") or []),
        "published_at": published_at,
        "checked_at": checked_at,
        "supported_claims": list(group.get("supported_claims") or []),
        "confidence": event.confidence,
        "corroboration_label": event.corroboration_label,
        "superseded_by": superseded_by or None,
        "retraction_status": news_intelligence.RETRACTION_SUPERSEDED if superseded_by else None,
    }


@app.get(
    "/v1/external/players/{player_id}/news",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_player_news(
    player_id: str,
    limit: int = MAX_PLAYER_NEWS_LIMIT,
) -> dict[str, Any]:
    """Structured news evidence for one player — Phase 2 of coridian_'s
    external content-posting bot wish list (docs/external-api-contract.md):
    confirmed player id, every independent corroborating source link,
    publish timestamp, the specific supporting evidence phrases, real
    structured-status corroboration, and a conservative, mechanically-scoped
    supersession signal. Always 200: an unknown player id or one with no
    recent actionable coverage returns an empty `items` list rather than a
    4xx, same honesty-over-error discipline as the projections endpoints.

    Shares its article source and player-name phrase-match with
    `GET /v1/players/{id}/news` (the per-user-session version just above) —
    the generic news pool is already league/session-independent
    (`modules.news.enriched_news_pool`), so this route needs no session at
    all, only the static API key. It additionally groups matching articles
    by `modules.news_intelligence`'s per-claim `event_identity` (collapsing
    syndicated/aggregator reposts of the same claim into one item with every
    independent source URL attached, not just one representative link),
    joins real Sleeper structured-status corroboration
    (`corroborate_with_structured_injury` — the exact building block
    Alerts/Dashboard already use, not a second label scheme), and runs
    `detect_supersession` across this player's own event history to flag
    the narrow, mechanically-detectable retraction case described in the
    contract doc.
    """

    if not 1 <= limit <= MAX_PLAYER_NEWS_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_PLAYER_NEWS_LIMIT}.")

    players_df = _external_news_players_frame()
    row_matches = (
        players_df[players_df["player_id"].astype(str) == str(player_id)]
        if not players_df.empty and "player_id" in players_df.columns
        else players_df
    )
    player_name = str(row_matches.iloc[0].get("name") or "").strip() if not row_matches.empty else ""
    if not player_name:
        return {"ok": True, "player_id": str(player_id), "items": []}

    news_cache.schedule_news_cache_refresh()
    enriched = news_cache.enriched_news_pool()
    matches = [
        item
        for item in enriched
        if item.get("signal_primary_event") in _ACTIONABLE_NEWS_EVENTS
        and news_identity.article_names_player(item, str(player_id), player_name, players_df)
    ]

    groups = news_intelligence.group_player_events_by_identity(
        matches, player_id=str(player_id), player_name=player_name
    )
    for group in groups:
        group["event"] = news_intelligence.corroborate_with_structured_injury(
            group["event"], players_df
        )
    superseded = news_intelligence.detect_supersession(groups)
    checked_at = datetime.now(timezone.utc).isoformat()
    from modules import gsis_crosswalk as _gsis_crosswalk  # None unless DYNASTYGM_NEWS_EVIDENCE_FETCH=1

    identity = external_news_contract.resolve_player_identity(
        players_df, str(player_id), player_name, gsis_crosswalk=_gsis_crosswalk.load_gsis_crosswalk()
    )
    now_ts = int(time.time())

    items = [
        _external_news_payload(
            player_id,
            group,
            superseded_by=superseded.get(group["event"].event_identity, ""),
            checked_at=checked_at,
            identity=identity,
            now_ts=now_ts,
        )
        for group in groups[:limit]
    ]
    return {"ok": True, "player_id": str(player_id), "items": items}


@app.get(
    "/v1/external/news",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_news_feed(
    cursor: str | None = None,
    since: str | None = None,
    limit: int = external_news_feed.DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Cursor feed of ingested NFL headlines for the content bot
    (docs/external-api-contract.md, "News feed"). Reads the store written by
    the scheduled ingest (scripts/ingest_news.py); never fetches from the
    network and never writes. Use ``next_cursor`` from the previous response
    as ``cursor``; ``since`` (ISO-8601 or epoch seconds) is only for the
    first call and defaults to the last 24 hours.
    """

    if not 1 <= limit <= external_news_feed.MAX_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {external_news_feed.MAX_LIMIT}.")
    try:
        external_news_feed.decode_cursor(cursor)
        external_news_feed.parse_since(since)
    except external_news_feed.CursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    store = news_ingest.open_store(use_cache=True)
    players_df, index = news_identity.load_index(PLAYERS_DB_PATH)
    return external_news_feed.build_feed(
        store, players_df=players_df, index=index, cursor=cursor, since=since, limit=limit
    )


# ---------------------------------------------------------------------------
# External (bot) rating-change history — Phase 3, last and biggest piece of
# coridian_'s external content-posting bot wish list (full contract:
# docs/external-api-contract.md). Gated by the exact same
# require_external_api_key dependency as Phases 1/2 above; this section adds
# no new auth. Unlike Phases 1/2, this is NOT computed fresh on every
# request — it reads a real, persisted daily snapshot table
# (modules.player_rating_history, docs/supabase_player_rating_snapshots.sql)
# written once a day by .github/workflows/player-rating-snapshot.yml.
# ---------------------------------------------------------------------------


def _rating_history_corroborating_news(
    player_id: str,
    player_name: str,
    *,
    direction: int,
    window_start_iso: str,
    window_end_iso: str,
) -> list[dict[str, Any]]:
    """Real, checkable corroboration for one rating-history delta: actionable
    news events about this player whose own `event_direction` agrees with
    the rating's direction and whose article published inside this
    snapshot's window (previous snapshot_date -> current snapshot_date).

    Deliberately reuses the exact same building blocks
    GET /v1/external/players/{id}/news (Phase 2, just above) already uses —
    `news_cache.enriched_news_pool`, `news_signal.contains_phrase`,
    `news_intelligence.group_player_events_by_identity` — rather than a
    second, parallel news pipeline. Sorted newest-first so
    `player_rating_history.explain_rating_change` picks the most recent
    corroborating event when more than one qualifies.

    Fails soft to `[]` on any error: a news-lookup hiccup must never break
    the rating-history endpoint, it only means the explanation falls back
    to the honest "no significant driver identified."
    """

    try:
        if not player_name or direction == 0:
            return []
        wanted_direction = "up" if direction > 0 else "down"
        news_cache.schedule_news_cache_refresh()
        enriched = news_cache.enriched_news_pool()
        matches = [
            item
            for item in enriched
            if item.get("signal_primary_event") in _ACTIONABLE_NEWS_EVENTS
            and news_signal.contains_phrase(news_signal.article_text(item), player_name)
        ]
        groups = news_intelligence.group_player_events_by_identity(
            matches, player_id=str(player_id), player_name=player_name
        )
        corroborating: list[dict[str, Any]] = []
        for group in groups:
            event: news_intelligence.FootballEvent = group["event"]
            if event.event_direction != wanted_direction:
                continue
            published_at = (
                datetime.fromtimestamp(event.article_time, tz=timezone.utc).isoformat()
                if event.article_time and event.article_time > 0
                else None
            )
            if published_at is None or not (window_start_iso <= published_at <= window_end_iso):
                continue
            corroborating.append(
                {"description": event.explanation, "published_at": published_at, "confidence": event.confidence}
            )
        corroborating.sort(key=lambda row: row["published_at"], reverse=True)
        return corroborating
    except Exception:
        return []


@app.get(
    "/v1/external/players/{player_id}/rating-history",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_player_rating_history(player_id: str) -> dict[str, Any]:
    """Previous/current 0-99 overall rating, the delta between them, the
    current snapshot's effective date, and a short, honest explanation —
    Phase 3 of coridian_'s external content-posting bot wish list
    (docs/external-api-contract.md).

    Backed by modules.player_rating_history's daily Supabase snapshot table
    (docs/supabase_player_rating_snapshots.sql), written once a day by
    .github/workflows/player-rating-snapshot.yml — NOT computed fresh on
    every request the way Phase 1's projections are. Until that table
    exists and the sweep has actually run for 2+ days there is no real
    history to report: this always returns 200 with
    `status: "insufficient_history"` and every comparison field null rather
    than a fabricated baseline or delta — the same honesty discipline
    Phase 1's non-"ok" projection statuses and Phase 2's supersession scope
    already establish in this file.
    """

    config = player_rating_history.load_rating_snapshot_config()
    snapshots = player_rating_history.fetch_rating_history(config, str(player_id), limit=2)

    if len(snapshots) < 2:
        current = snapshots[0] if snapshots else None
        return {
            "player_id": str(player_id),
            "status": "insufficient_history",
            "previous_rating": None,
            "current_rating": player_rating_history.snapshot_rating(current) if current else None,
            "delta": None,
            "effective_at": current.get("snapshot_date") if current else None,
            "explanation": None,
        }

    current, previous = snapshots[0], snapshots[1]
    current_rating = player_rating_history.snapshot_rating(current)
    previous_rating = player_rating_history.snapshot_rating(previous)
    if current_rating is None or previous_rating is None:
        # Stored rows should always carry a valid 0-99 int (see
        # build_snapshot_rows' own range check) — this is a defensive
        # honesty fallback, not an expected path.
        return {
            "player_id": str(player_id),
            "status": "insufficient_history",
            "previous_rating": None,
            "current_rating": current_rating,
            "delta": None,
            "effective_at": current.get("snapshot_date"),
            "explanation": None,
        }

    delta = current_rating - previous_rating
    effective_at = current.get("snapshot_date")

    player_name = ""
    try:
        players_df = rankings.load_players(PLAYERS_DB_PATH)
        if players_df is None or players_df.empty:
            players_df = rankings.build_players_table(PLAYERS_DB_PATH)
        row_matches = players_df[players_df["player_id"] == str(player_id)] if players_df is not None and not players_df.empty else None
        if row_matches is not None and not row_matches.empty:
            player_name = str(row_matches.iloc[0].get("name") or "").strip()
    except Exception:
        player_name = ""

    corroborating: list[dict[str, Any]] = []
    if delta != 0 and player_name:
        previous_date = str(previous.get("snapshot_date") or "")
        current_date = str(current.get("snapshot_date") or "")
        corroborating = _rating_history_corroborating_news(
            str(player_id),
            player_name,
            direction=1 if delta > 0 else -1,
            window_start_iso=f"{previous_date}T00:00:00+00:00",
            window_end_iso=f"{current_date}T23:59:59+00:00",
        )

    explanation = player_rating_history.explain_rating_change(delta=delta, corroborating_events=corroborating)

    return {
        "player_id": str(player_id),
        "status": "ok",
        "previous_rating": previous_rating,
        "current_rating": current_rating,
        "delta": delta,
        "effective_at": effective_at,
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# External (bot) player background profile — Phase 4 addition to
# coridian_'s external content-posting bot wish list (full contract:
# docs/external-api-contract.md). Gated by the exact same
# require_external_api_key dependency as Phases 1-3 above; this section
# adds no new auth. All business logic lives in
# modules.player_background_profile — this route handler is a thin wrapper,
# the same split Phase 1's projections routes already established with
# modules.player_projections.project_player_week.
# ---------------------------------------------------------------------------


@app.get(
    "/v1/external/players/{player_id}/background",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_player_background(
    player_id: str,
    season: int | None = None,
) -> dict[str, Any]:
    """One player's background profile for the external content-posting
    bot: real, non-monetary contract-timeline context sourced from
    nflverse's public `historical_contracts` dataset (Priority 1 —
    `status: "unavailable"` with a specific reason whenever this player
    can't be matched to that dataset unambiguously, never a guess), real
    NFL team-situation context (Priority 2: teammates, Sleeper's own
    published depth chart, recent workload), and real historical PPR
    production with an honestly-unavailable standard/box-score sibling
    (Priority 3) — see
    `modules.player_background_profile.build_player_background_profile`
    and `docs/external-api-contract.md` for the full field-by-field
    contract. Always 200 once authenticated: an unknown player id returns
    the full shape with every section `"unavailable"` rather than a 4xx,
    the same honesty-over-error discipline every other `/v1/external/*`
    route in this file already uses.
    """

    return player_background_profile.build_player_background_profile(str(player_id), season=season)


# ---------------------------------------------------------------------------
# External (bot) completed-week actual production: the "Weekly recap"
# section of docs/external-api-contract.md. Business logic lives in
# modules.weekly_box_scores; these handlers are thin wrappers gated by the
# same require_external_api_key dependency as every other /v1/external/*
# route (and rate limited by the same global middleware).
# ---------------------------------------------------------------------------


@app.get(
    "/v1/external/players/{player_id}/week-result",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_player_week_result(
    player_id: str,
    week: int,
    season: int | None = None,
) -> dict[str, Any]:
    """One player's real stat line for one completed regular-season week:
    Sleeper's own box score and PPR/half-PPR/standard points, with the same
    identity/team/position/game fields as the projections endpoints. Always
    200 once authenticated (422 only for a week outside 1-18): a bye, an
    unfinished game, a stat line cached before the game could have ended,
    or an unknown player all come back as a non-"ok" `status` with every
    stat null, never a guess. Never substitutes a projection or rating.
    """

    try:
        return weekly_box_scores.build_player_week_result(str(player_id), int(week), season)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/v1/external/recap",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_week_recap(
    week: int,
    season: int | None = None,
    position: str | None = None,
    scoring_format: str = "ppr",
    limit: int = weekly_box_scores.DEFAULT_TOP_LIMIT,
) -> dict[str, Any]:
    """The week's real results for a recap post: top performers (overall
    and per position) and notable statistical lines, ranked by Sleeper's own
    published points, plus the week's real game-level completion status.
    Only final, fully captured stat lines are ranked. See
    `modules.weekly_box_scores.build_week_recap`.
    """

    try:
        return weekly_box_scores.build_week_recap(
            int(week),
            season,
            position=position,
            scoring_format=str(scoring_format or "ppr").strip().lower(),
            limit=int(limit),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _external_trades_args(format: str, lens: str) -> tuple[str, str]:
    fmt, lens_key = str(format or "").strip().lower(), str(lens or "").strip().lower()
    if fmt not in external_interesting_trades.FORMATS:
        raise HTTPException(status_code=422, detail="format must be one of: " + ", ".join(external_interesting_trades.FORMATS))
    if lens_key not in external_interesting_trades.LENSES:
        raise HTTPException(status_code=422, detail="lens must be one of: " + ", ".join(external_interesting_trades.LENSES))
    return fmt, lens_key


@app.get(
    "/v1/external/trades/interesting",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_interesting_trades(
    format: str = "superflex",
    lens: str = "ppr",
    type: str | None = None,
    limit: int = 5,
    min_spice: int = 0,
    exclude_ids: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Interesting, concrete trades for the ad/content bot (full contract:
    docs/external-trades-interesting.md). Public player data only: no league,
    roster or account is read. Each item is graded by the app's own Trade
    Analyzer engine against a reference roster. Deterministic daily rotation;
    `exclude_ids` / `since` keep the bot from repeating itself.
    """

    fmt, lens_key = _external_trades_args(format, lens)
    if not 1 <= limit <= 25:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 25.")
    if not 0 <= min_spice <= 100:
        raise HTTPException(status_code=422, detail="min_spice must be between 0 and 100.")
    types = [t.strip() for t in (type or "").split(",") if t.strip()]
    unknown = [t for t in types if t not in external_interesting_trades.TYPES]
    if unknown:
        raise HTTPException(status_code=422, detail="type must be one of: " + ", ".join(external_interesting_trades.TYPES))
    now = datetime.now(timezone.utc)
    try:
        since_at = external_interesting_trades.parse_since(since, now)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    excluded = [x.strip() for x in (exclude_ids or "").split(",") if x.strip()][:500]

    pool, mtime = external_interesting_trades.get_pool(PLAYERS_DB_PATH, fmt, lens_key, now)
    items = external_interesting_trades.select_items(
        pool, now=now, limit=limit, types=types or None, min_spice=min_spice, exclude_ids=excluded, since=since_at
    )
    return {
        "ok": True,
        "format": fmt,
        "lens": lens_key,
        "format_label": external_interesting_trades.lens_label(fmt, lens_key),
        "valuation": external_interesting_trades.VALUATION_LENS,
        "rotation_date": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "since_applied": since_at.isoformat() if since_at else None,
        "data_as_of": datetime.fromtimestamp(mtime, timezone.utc).isoformat() if mtime else None,
        "verdict_basis": "Trade Analyzer engine (trade_analyzer_fit + trade_offer_analyzer) run against a league-median reference roster of real players; not any user's roster.",
        "count": len(items),
        "available_types": list(external_interesting_trades.TYPES),
        "spice": external_interesting_trades.SPICE_DEFINITION,
        "items": items,
    }


@app.get(
    "/v1/external/trades/interesting/{item_id}/share-card.png",
    dependencies=[Depends(require_external_api_key)],
)
def get_external_interesting_trade_share_card(
    item_id: str,
    format: str = "superflex",
    lens: str = "ppr",
) -> Response:
    """Branded, QR-coded PNG for one feed item. Same renderer as the in-app
    share cards (modules.share_card_renderer) but fed from the public feed
    item, so no user token or roster is involved. The item must exist in the
    current pool for this format/lens; ids that rotated out of the data are
    a real 404, never a fabricated image."""

    fmt, lens_key = _external_trades_args(format, lens)
    pool, _ = external_interesting_trades.get_pool(PLAYERS_DB_PATH, fmt, lens_key)
    item = next((i for i in pool if i["id"] == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown or expired trade id for this format/lens.")
    public_item = {k: v for k, v in item.items() if not k.startswith("_")}
    card = share_recommendation_cards.build_trade_share_card(
        external_interesting_trades.idea_for_share_card(public_item),
        source_surface="external_trades",
        scoring_format="PPR" if lens_key == "ppr" else "TEP",
        my_team_name="Team A",
    )
    if not card.is_shareable:
        raise HTTPException(status_code=404, detail=card.decline_reason or "This trade cannot be rendered.")
    try:
        png = share_card_renderer.render_square_share_card_png(
            card,
            size=external_interesting_trades.SHARE_CARD_SIZE,
            destination=external_interesting_trades.SHARE_CARD_DESTINATION,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc) or "This trade cannot be rendered.") from exc
    return Response(content=png, media_type="image/png")


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


_GM_TARGET_PLAYER_IDS_TTL_SECONDS = 15


def _fetch_gm_target_player_ids(
    config: dict[str, Any], user_id: str, access_token: str, league_id: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(all target player_ids, untouchable-only player_ids) for trade idea generation.

    Fails soft to (empty, empty) — a GM Targets outage must never block Trade
    Hub or the Dashboard trade tile from generating ideas.

    Read-only hot path (8 call sites across Trade Hub/Trade Finder/Dashboard
    trade-idea generation) — cached the same way as saved_leagues/
    profile_fields/team_stance in this audit. Deliberately NOT applied to
    `_fetch_gm_target_rows` itself, which add_gm_target/set_gm_target_untouchable
    also call as a pre-write existence/cap check that must always see the
    latest row state.
    """

    if not user_id:
        return (), ()
    cache_key = redis_cache.build_cache_key("gm_target_player_ids", user_id, league_id)
    try:
        return redis_cache.redis_single_flight_cache(
            cache_key=cache_key,
            ttl_seconds=_GM_TARGET_PLAYER_IDS_TTL_SECONDS,
            compute=lambda: _fetch_gm_target_player_ids_uncached(config, user_id, access_token, league_id),
        )
    except Exception:
        return _fetch_gm_target_player_ids_uncached(config, user_id, access_token, league_id)


def _fetch_gm_target_player_ids_uncached(
    config: dict[str, Any], user_id: str, access_token: str, league_id: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
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
def get_gm_targets(league_id: str = Depends(resolve_league_path_id), user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
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
    # The plan's cap, so clients can say "Free: 2 of 3" without carrying a
    # copy of the number (same limit add_gm_target enforces below).
    profile = _fetch_profile_fields(config, user_id, access_token)
    is_pro = premium.is_at_least(profile.get("entitlement"), premium.PRO)
    return {
        "ok": True,
        "targets": [_project_gm_target(row) for row in rows],
        "limit": gm_targets.MAX_TARGETS_PREMIUM if is_pro else gm_targets.MAX_TARGETS_FREE,
        "free_limit": gm_targets.MAX_TARGETS_FREE,
        "is_premium": is_pro,
    }


@app.post("/v1/leagues/{league_id}/gm-targets")
def add_gm_target(
    payload: AddGmTargetRequest,
    # NOT resolved -- see resolve_league_path_id's docstring. GM Targets
    # rows are keyed by (user_id, league_id, player_id); the paired DELETE
    # below removes a row by that same exact key, so add/remove must keep
    # using whatever id the client is currently operating under, or a
    # remove issued right after an add (same session, id resolves forward
    # in between) could silently miss the row it just created.
    league_id: str,
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
        if premium.is_at_least(profile.get("entitlement"), premium.PRO)
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
    player_id: str,
    # NOT resolved -- see add_gm_target above and resolve_league_path_id's
    # docstring: must match on the exact (user_id, league_id, player_id)
    # key the row was stored under.
    league_id: str,
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
    player_id: str,
    payload: SetGmTargetUntouchableRequest,
    # NOT resolved -- see add_gm_target above and resolve_league_path_id's
    # docstring: must match on the exact (user_id, league_id, player_id)
    # key the row was stored under.
    league_id: str,
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


# ---------------------------------------------------------------------------
# College Football Prospect Scouting — crowdsourced shared signal (all users
# grade the same prospect pool; the aggregate feeds draft-class strength) +
# a personal watchlist layered on top. See modules/college_scouting.py and
# docs/supabase_college_scouting.sql (manual migration required — every
# handler below fails soft to empty/no-op if it isn't applied yet).
# ---------------------------------------------------------------------------


@app.get("/v1/scouting/prospects")
def get_scouting_prospects(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Shared prospect catalog + shared scouting aggregate + the caller's own
    report and watchlist status, in one round trip (powers the mobile
    College Prospects list screen).

    Fails soft: if the catalog or scouting_reports/prospect_watchlist aren't
    reachable yet (migration not applied), this still returns 200 with an
    empty/partial result rather than erroring the whole screen — same
    posture as every other Supabase-backed mobile feature in this file.
    There is no fabricated-data fallback: if the real catalog isn't
    available, ``prospects`` is simply empty (see
    modules/college_scouting.py's "NO FABRICATED DATA" docstring section),
    and the mobile screen's existing empty state ("No prospects yet") covers
    that honestly rather than inventing players.
    """

    if not _is_pro_caller(user):
        return {
            "ok": True,
            "prospects": [],
            "catalog_available": True,
            "reason": "premium_required",
            "is_premium": False,
            "upsell": _COLLEGE_SCOUTING_UPSELL,
        }

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")

    prospects, prospects_error = college_scouting.get_cached_all_prospects(config, access_token)
    reports, reports_error = college_scouting.get_cached_all_scouting_reports(config, access_token)
    watchlist_ids: list[str] = []
    if user_id:
        watchlist_rows, _watchlist_error = account_store.fetch_rows(
            config, access_token, college_scouting.WATCHLIST_TABLE, user_id=user_id
        )
        watchlist_ids = [str(row.get("prospect_id")) for row in watchlist_rows if row.get("prospect_id")]

    rows = college_scouting.build_prospect_views(
        prospects, reports, my_user_id=user_id, watchlist_prospect_ids=watchlist_ids
    )
    return {
        "ok": True,
        "prospects": rows,
        "catalog_available": not bool(prospects_error),
        "reason": "scouting_reports_not_available" if reports_error else "",
        "is_premium": True,
        "upsell": None,
    }


class SubmitScoutingReportRequest(BaseModel):
    grade: int
    round_projection: int | None = None
    note: str = ""


@app.post("/v1/scouting/prospects/{prospect_id}/report")
def submit_scouting_report(
    prospect_id: str,
    body: SubmitScoutingReportRequest,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Upsert the caller's own scouting grade for one prospect.

    Idempotent — one report per (user, prospect) (scouting_reports' primary
    key), so re-submitting simply replaces the caller's prior grade/note.
    Never writes any other user's row and never touches the aggregate
    directly — the aggregate is always recomputed from every report by
    modules.college_scouting.aggregate_prospect_scouting.
    """

    grade = college_scouting.normalize_grade(body.grade)
    if grade is None:
        raise HTTPException(
            status_code=422,
            detail=f"grade must be an integer {college_scouting.MIN_GRADE}-{college_scouting.MAX_GRADE}.",
        )
    round_projection = college_scouting.normalize_round_projection(body.round_projection)
    if body.round_projection is not None and round_projection is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "round_projection must be an integer "
                f"{college_scouting.MIN_ROUND_PROJECTION}-{college_scouting.MAX_ROUND_PROJECTION} or omitted."
            ),
        )

    if not _is_pro_caller(user):
        return {"ok": False, "reason": "premium_required", "is_premium": False, "upsell": _COLLEGE_SCOUTING_UPSELL}

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    payload: dict[str, Any] = {
        "user_id": user_id,
        "prospect_id": prospect_id,
        "grade": grade,
        "note": body.note.strip()[:280],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if round_projection is not None:
        payload["round_projection"] = round_projection
    ok, error = account_store.upsert_row(
        config,
        access_token,
        college_scouting.SCOUTING_REPORTS_TABLE,
        payload,
        on_conflict="user_id,prospect_id",
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


@app.delete("/v1/scouting/prospects/{prospect_id}/report")
def delete_scouting_report(
    prospect_id: str,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Remove the caller's own scouting report (their grade stops
    contributing to the shared aggregate on the next read)."""

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}
    ok, error = account_store.delete_rows(
        config,
        access_token,
        college_scouting.SCOUTING_REPORTS_TABLE,
        query=f"user_id=eq.{user_id}&prospect_id=eq.{prospect_id}",
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


@app.post("/v1/scouting/watchlist/{prospect_id}")
def add_prospect_to_watchlist(
    prospect_id: str,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Follow a prospect on the caller's personal watchlist. Idempotent."""

    if not _is_pro_caller(user):
        return {"ok": False, "reason": "premium_required", "is_premium": False, "upsell": _COLLEGE_SCOUTING_UPSELL}

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}
    ok, error = account_store.upsert_row(
        config,
        access_token,
        college_scouting.WATCHLIST_TABLE,
        {"user_id": user_id, "prospect_id": prospect_id},
        on_conflict="user_id,prospect_id",
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


@app.delete("/v1/scouting/watchlist/{prospect_id}")
def remove_prospect_from_watchlist(
    prospect_id: str,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Unfollow a prospect. Never touches scouting_reports — removing a
    watchlist follow does not delete the caller's scouting grade, if any."""

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}
    ok, error = account_store.delete_rows(
        config,
        access_token,
        college_scouting.WATCHLIST_TABLE,
        query=f"user_id=eq.{user_id}&prospect_id=eq.{prospect_id}",
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {"ok": True, "reason": ""}


def _project_award(badge: player_awards.PlayerBadge) -> dict[str, Any]:
    return {
        "badge_id": badge.badge_id,
        "category": badge.category,
        "family": badge.family,
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
    # IANA zone (e.g. "America/Chicago") for push quiet hours. Optional;
    # unknown/invalid is stored as unknown and the sweep assumes New York.
    timezone: str = ""


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
        timezone=payload.timezone,
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
        title="FantasyDesk",
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
# Set during onboarding's last step ("How much dynasty experience do you
# have?"), consumed by web-next/mobile lib/experienceCopy.ts to decide
# whether a page shows beginner helper text. None/unset is a real third
# state (an existing account from before this question existed, or one who
# skipped onboarding), distinct from "beginner" — never defaulted to either
# value. "new_to_fantasy" added 2026-10-27 (onboarding audit P1): a third,
# more-granular level alongside the original two. Purely additive — the
# original "beginner"/"advanced" values, and every account that already has
# one stored, keep meaning exactly what they always did.
EXPERIENCE_LEVEL_VALUES = {"beginner", "advanced", "new_to_fantasy"}
# Optional, skippable "what's your goal this season?" chip added alongside
# experience level (same onboarding audit). Stored the same way: a plain
# string in the user_settings blob, "" (sent explicitly) clears it back to
# unset, matching the existing last_league_id convention below.
EXPERIENCE_GOAL_VALUES = {"win_now", "rebuilding", "exploring"}


def _device_preferences_from_settings(settings: dict[str, Any]) -> dict[str, Any]:
    density = str(settings.get("ui_density") or "guided")
    if density not in UI_DENSITY_VALUES:
        density = "guided"
    theme_mode = str(settings.get("theme_mode") or "dark")
    if theme_mode not in THEME_MODE_VALUES:
        theme_mode = "dark"
    last_league_id = str(settings.get("last_league_id") or "")
    last_league_name = str(settings.get("last_league_name") or "")
    experience_level = settings.get("experience_level")
    if experience_level not in EXPERIENCE_LEVEL_VALUES:
        experience_level = None
    experience_goal = settings.get("experience_goal")
    if experience_goal not in EXPERIENCE_GOAL_VALUES:
        experience_goal = None
    return {
        "ui_density": density,
        "theme_mode": theme_mode,
        "experience_level": experience_level,
        "experience_goal": experience_goal,
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
    experience_level: str | None = None
    # None = not sent, leave untouched (same partial-update convention as
    # every other field here). "" = sent explicitly to clear the goal back
    # to unset (same convention last_league_id already uses). Any other
    # value must be one of EXPERIENCE_GOAL_VALUES.
    experience_goal: str | None = None


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
    if body.experience_level is not None and body.experience_level not in EXPERIENCE_LEVEL_VALUES:
        raise HTTPException(
            status_code=422,
            detail="experience_level must be one of: " + ", ".join(EXPERIENCE_LEVEL_VALUES),
        )
    if (
        body.experience_goal is not None
        and body.experience_goal != ""
        and body.experience_goal not in EXPERIENCE_GOAL_VALUES
    ):
        raise HTTPException(
            status_code=422,
            detail="experience_goal must be one of: " + ", ".join(EXPERIENCE_GOAL_VALUES),
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
    if body.experience_level is not None:
        settings["experience_level"] = body.experience_level
    if body.experience_goal is not None:
        settings["experience_goal"] = body.experience_goal
    payload = account_store.build_user_settings_payload(user_id=user_id, settings=settings)
    ok, error = account_store.upsert_user_settings(config, access_token, payload)
    if not ok:
        return {"ok": False, **_device_preferences_from_settings(settings)}
    return {"ok": True, **_device_preferences_from_settings(settings)}


# Decision Memory v1 ("structured picks," per explicit product direction —
# not free text): originally a durable per-league GM stance, reusing the
# TeamStrategy values Trade Hub/Trade Analyzer already offer as an
# in-session-only picker (contender/fringe_contender/retool/rebuild/tank),
# stored in the user_settings blob under "team_strategy_by_league".
#
# GM Stance / Team Situation merge (product decision, 2026-09-26): that
# separate "team_strategy_by_league" storage is retired. Team Situation
# (modules.team_stance, the /team-stance endpoints below) is now the single
# source of truth for this input — see modules.team_stance's module
# docstring and team_strategy_for_stance() for the full mapping. This
# TEAM_STRATEGY_VALUES set is kept only to validate the legacy
# POST /gm-stance write path below (still-installed pre-merge mobile builds
# calling it must not silently corrupt storage), and because
# modules.trade_hub_engine.apply_strategy_age_curve is still keyed on these
# same five concrete strings — the real math is unchanged, only its input
# source moved.
TEAM_STRATEGY_VALUES = {"contender", "fringe_contender", "retool", "rebuild", "tank"}

# Reverse of modules.team_stance.team_strategy_for_stance's mapping, used
# only by the legacy POST /gm-stance write-through below.
_LEGACY_STRATEGY_TO_STANCE: dict[str, str] = {
    "contender": team_stance.STANCE_COMPETING,
    "fringe_contender": team_stance.STANCE_COMPETING,
    "retool": team_stance.STANCE_BALANCED,
    "rebuild": team_stance.STANCE_REBUILDING,
    "tank": team_stance.STANCE_REBUILDING,
}


def _fetch_gm_stance_with_set_flag(
    config: dict, access_token: str, *, user_id: str, league_id: str
) -> tuple[str, bool]:
    """GM Stance merged into Team Situation (product decision, 2026-09-26):
    this now reads the SAME team_stance row get_team_stance/set_team_stance
    use (via _fetch_team_stance), mapped through
    modules.team_stance.team_strategy_for_stance into the strategy key
    apply_strategy_age_curve expects — instead of the old, now-retired
    "team_strategy_by_league" user_settings key. `is_set` still distinguishes
    "the user actually declared a Team Situation" from "nothing declared
    yet, showing the fallback" — used only by get_gm_stance to power the
    mobile in-app "not set yet" nudge; nothing else needs it.
    """

    stance = _fetch_team_stance(config, user_id, access_token, league_id)
    return team_stance.team_strategy_for_stance(stance), bool(stance)


@app.get("/v1/leagues/{league_id}/gm-stance")
def get_gm_stance(league_id: str = Depends(resolve_league_path_id), user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
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
    # `null` (or an omitted field) clears the stance instead of setting one.
    # Pre-merge behavior note: this used to reset the old, now-retired
    # "team_strategy_by_league" storage to unset. Team Situation has no
    # "unset" concept (see modules.team_stance) — clearing is now a no-op,
    # see update_gm_stance's docstring.
    strategy: str | None = None


@app.post("/v1/leagues/{league_id}/gm-stance")
def update_gm_stance(
    body: UpdateGmStanceRequest,
    # NOT resolved -- see resolve_league_path_id's docstring: this upserts
    # a preference row keyed by (user_id, league_id). The matching GET
    # above IS resolved, so a stance set under a stale id self-heals the
    # next time it's read back and re-declared under the current id.
    league_id: str,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Deprecated write path, kept only so a pre-merge mobile build still
    calling this endpoint doesn't silently break (GM Stance / Team Situation
    merge, product decision 2026-09-26): the separate "team_strategy_by_league"
    user_settings storage this used to write is retired, so a legacy
    `strategy` choice here now writes through to the SAME team_stance row
    set_team_stance uses, via _LEGACY_STRATEGY_TO_STANCE (the reverse of
    modules.team_stance.team_strategy_for_stance's mapping). Clearing
    (`strategy: null`) is a no-op: Team Situation has no "unset" concept, so
    there is nothing left to revert to "Auto."

    Current mobile builds no longer call this — they read/write Team
    Situation directly via GET/POST /v1/leagues/{id}/team-stance.
    """

    clearing = body.strategy is None
    if not clearing and body.strategy not in TEAM_STRATEGY_VALUES:
        raise HTTPException(
            status_code=422,
            detail="strategy must be one of: " + ", ".join(TEAM_STRATEGY_VALUES),
        )

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")

    if clearing:
        current_stance = _fetch_team_stance(config, user_id, access_token, league_id)
        return {
            "ok": True,
            "strategy": team_stance.team_strategy_for_stance(current_stance),
            "is_set": bool(current_stance),
        }

    stance_key = _LEGACY_STRATEGY_TO_STANCE[str(body.strategy)]
    ok, error = account_store.upsert_row(
        config,
        access_token,
        team_stance.STANCE_TABLE,
        {"user_id": user_id, "league_id": league_id, "stance": stance_key},
        on_conflict="user_id,league_id",
    )
    if not ok:
        return {"ok": False, "strategy": "retool", "is_set": False}
    return {
        "ok": True,
        "strategy": team_stance.team_strategy_for_stance(stance_key),
        "is_set": True,
    }


# Team Situation (Decision Memory v1 gap, #232 follow-up): a plain, fixed
# three-way declaration (Rebuilding/Competing/Balanced), stored in its own
# dedicated table (modules.team_stance, RLS-scoped like gm_targets — not a
# user_settings JSON blob).
#
# GM Stance / Team Situation merge (product decision, 2026-09-26): Team
# Situation used to be a SEPARATE, presentation-only mechanism from GM
# Stance (contender/fringe_contender/retool/rebuild/tank, which fed
# modules.trade_hub_engine's age-curve and changed valuation). That
# separation is gone: Team Situation is now the single source of truth for
# BOTH — it still appends a rationale-TEXT clause
# (modules.trade_ideas.apply_team_stance_framing) AND, via
# modules.team_stance.team_strategy_for_stance, drives the same real
# age-curve/pick-multiplier valuation math GM Stance used to drive (see
# _fetch_gm_stance_with_set_flag above). See modules.team_stance's module
# docstring for the full mapping and rationale.
# coridian_, 2026-10-19: continuing the site-wide load-time audit (see
# _fetch_saved_leagues_cached / _fetch_profile_fields above) -- this is a
# third uncached hot path, called from ~11 different league-scoped
# endpoints (Dashboard, My Team, Matchup, Trade Hub, Trade Finder, Trade
# Analyzer, Waivers, GM Plan, ...), each paying its own full uncached
# Supabase round trip for a value that only changes when the user
# explicitly declares a new stance.
_TEAM_STANCE_TTL_SECONDS = 15


def _fetch_team_stance(config: dict, user_id: str, access_token: str, league_id: str) -> str:
    """Best-effort read — any failure/missing row/missing table returns ""
    (no stance declared), never raises. A Team Situation outage must never
    block Trade Hub, Trade Finder, or the Dashboard trade tile."""

    if not user_id:
        return ""
    cache_key = redis_cache.build_cache_key("team_stance", user_id, league_id)
    try:
        return redis_cache.redis_single_flight_cache(
            cache_key=cache_key,
            ttl_seconds=_TEAM_STANCE_TTL_SECONDS,
            compute=lambda: _fetch_team_stance_uncached(config, user_id, access_token, league_id),
        )
    except Exception:
        return _fetch_team_stance_uncached(config, user_id, access_token, league_id)


def _fetch_team_stance_uncached(config: dict, user_id: str, access_token: str, league_id: str) -> str:
    rows, error = account_store.fetch_rows(
        config,
        access_token,
        team_stance.STANCE_TABLE,
        user_id=user_id,
        extra_query=f"league_id=eq.{league_id}&select=stance&limit=1",
    )
    if error or not rows:
        return ""
    return team_stance.normalize_stance(rows[0].get("stance"))


@app.get("/v1/leagues/{league_id}/team-stance")
def get_team_stance(league_id: str = Depends(resolve_league_path_id), user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """The caller's declared Team Situation for this league — "" when unset.

    Drives both trade-idea rationale framing AND real valuation adjustments
    (see module comment above); fails soft to "" rather than erroring the
    screen if storage isn't reachable.
    """

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    stance = _fetch_team_stance(config, user_id, access_token, league_id)
    return {
        "ok": True,
        "stance": stance,
        "options": list(team_stance.STANCE_OPTIONS),
        # Same computation get_gm_stance returns as `strategy` — included here
        # too so the client can read the real backend-computed value after
        # this round-trip instead of re-deriving it itself (see
        # modules.team_stance.team_strategy_for_stance).
        "strategy": team_stance.team_strategy_for_stance(stance),
    }


class SetTeamStanceRequest(BaseModel):
    stance: str


@app.post("/v1/leagues/{league_id}/team-stance")
def set_team_stance(
    body: SetTeamStanceRequest,
    # NOT resolved -- see update_gm_stance above and resolve_league_path_id's
    # docstring. Same (user_id, league_id) preference-row shape, same
    # self-healing-via-the-GET-endpoint argument.
    league_id: str,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Set (upsert) the caller's declared Team Situation for this league."""

    stance_key = team_stance.normalize_stance(body.stance)
    if not stance_key:
        raise HTTPException(
            status_code=422,
            detail="stance must be one of: " + ", ".join(team_stance.STANCE_OPTIONS),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        return {"ok": False, "reason": "not_available"}

    ok, error = account_store.upsert_row(
        config,
        access_token,
        team_stance.STANCE_TABLE,
        {"user_id": user_id, "league_id": league_id, "stance": stance_key},
        on_conflict="user_id,league_id",
    )
    if not ok:
        return {"ok": False, "reason": "not_available"}
    return {
        "ok": True,
        "stance": stance_key,
        "strategy": team_stance.team_strategy_for_stance(stance_key),
    }


def _project_briefing_item_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": payload.get("category"),
        "headline": payload.get("headline"),
        "reason": payload.get("reason"),
        "supporting_context": payload.get("supporting_context"),
        "destination": payload.get("destination"),
        "route_player_id": payload.get("route_player_id") or "",
        "route_player_name": payload.get("route_player_name") or "",
        # Real player identity for the compact player module — sourced from
        # the same valued-player row the tile itself was built from
        # (dashboard_engine.py); "" / None when this tile's underlying row
        # genuinely lacks the field, never fabricated. Not every
        # route_player_id-bearing tile populates these yet, so the client
        # must handle empty/None gracefully.
        "route_player_position": payload.get("route_player_position") or "",
        "route_player_team": payload.get("route_player_team") or "",
        "route_player_tier": payload.get("route_player_tier") or "",
        "route_player_score": _clean_json_value(payload.get("route_player_score")),
        "route_player_injury_status": payload.get("route_player_injury_status") or "",
        "mentioned_players": list(payload.get("mentioned_players") or []),
        "recommendation_narrative": payload.get("recommendation_narrative"),
        "presentation": payload.get("presentation"),
        "recommendation_id": payload.get("recommendation_id") or "",
        "tier_label": payload.get("tier_label") or "",
    }


def _is_trade_briefing_item(item: Any) -> bool:
    presentation = item.to_dict().get("presentation")
    return isinstance(presentation, dict) and "trade_package" in presentation


def _project_briefing_item(item: Any) -> dict[str, Any]:
    return _project_briefing_item_payload(item.to_dict())


# Matches web's app.py `visible_action_items = action_center_items if
# is_premium else action_center_items[:4]` — the free-tier cap on Today's
# Game Plan.
FREE_DASHBOARD_VISIBLE_ITEMS = premium_benefits.FREE_NEXT_MOVE_ITEMS


@app.get("/v1/leagues/{league_id}/dashboard")
@_with_sleeper_as_of
def get_league_dashboard(
    league_id: str = Depends(resolve_league_path_id),
    lens: str = "Dynasty",
    defer_trade_ideas: bool = False,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """The caller's "Next Move" briefing for this league.

    `defer_trade_ideas=true` is the progressive first call: it returns the
    same payload minus the Top Trade Opportunity tile (the trade-idea search
    is the largest single piece of cold compute that is not needed to paint
    the page) and marks itself with `trade_ideas_deferred: true`. Clients
    follow it with the plain call, which is byte-for-byte the pre-existing
    response. The flag is never set on a response that already has the tile.

    Shares the same composition pipeline as the web app's Dashboard
    (modules.dashboard_workflow.organize_dashboard_items ->
    modules.daily_gm_briefing.compose_daily_gm_briefing) and the same
    underlying engines for each tile (modules.team_eval,
    modules.trade_analyzer_fit, modules.injury_ui, modules.waivers_logic) via
    modules.dashboard_engine — see that module's docstring for why it's a
    fresh composition rather than importing app.py directly (modules/ never
    imports app.py). Includes a Top Trade Opportunity tile fed by the same
    Trade Hub engine (modules.trade_hub_engine), using the caller's
    declared Team Situation for this league (see get_team_stance, mapped
    via modules.team_stance.team_strategy_for_stance) rather than a
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

    # Zach, screenshot: Dashboard crashed with a generic client error for a
    # league still mid-draft ("Something went wrong. It's been logged").
    # Root cause: DashboardContent.tsx reads `data.entitlement.hidden_count`
    # unconditionally, and DashboardResponse's own TS type declares
    # `entitlement`/`quiet_reason` as always-present — but every early-return
    # branch below omitted both, a real contract violation, not just a
    # missing frontend null-check. One shared builder so all of them match
    # the full response's exact shape (web-next/src/lib/api.ts's
    # DashboardResponse) instead of drifting independently again.
    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)

    def _empty_dashboard_response(reason_value: str) -> dict[str, Any]:
        return {
            "ok": True,
            "items": [],
            "quiet": True,
            "quiet_reason": reason_value,
            "team_snapshot": None,
            "reason": reason_value,
            "entitlement": {
                "is_premium": is_premium,
                "visible_count": 0,
                "hidden_count": 0,
                "free_limit": FREE_DASHBOARD_VISIBLE_ITEMS,
            },
            "this_week": this_week.not_ready_this_week(reason_value),
        }

    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return _empty_dashboard_response(reason)

    # coridian_, 2026-10-19: real "timed out"/slow-load complaints led to a
    # perf audit that found this check used to run AFTER sleeper.get_league
    # and the full build_valued_players_frame_cached pipeline (valuing the
    # WHOLE league's eligible player pool) — real, measured production
    # latency: an empty-roster caller (still drafting, or genuinely no
    # roster) paid that entire cost just to then throw it away on this
    # early return. roster_player_ids only ever depends on my_roster, which
    # is already resolved above — moved first so this cheapest possible
    # response path no longer pays for work it never uses.
    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_player_ids:
        return _empty_dashboard_response("empty_roster")

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)
    # Imported (ESPN / Fleaflicker / MFL) leagues: the platform's current week and
    # this team's real lineup, fail-soft; no waiver or trade engine (see
    # _external_dashboard_context).
    is_external = external_leagues.is_external_league_key(league_id)
    if is_external:
        league, my_roster = _external_dashboard_context(league_id, league, my_roster)

    # Same (league_id, lens)-scoped cache /rankings and friends share — see
    # league_value_settings.build_valued_players_frame_cached's docstring.
    # Dashboard is the app's home screen, opened on every session, so this
    # was previously the single most frequent re-run of the uncached chain.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if valued.empty:
        return _empty_dashboard_response("no_player_data")

    score_field = league_value_settings.valuation_score_field(lens)

    rosters = sleeper.get_rosters(league_id)
    all_rostered_player_ids: set[str] = set()
    for roster in rosters:
        all_rostered_player_ids.update(str(pid) for pid in (roster.get("players") or []))

    # One fetch of the declared Team Situation feeds BOTH consumers below:
    # `team_strategy` (mapped, for the real age-curve/pick-multiplier
    # valuation math GM Stance used to drive — see
    # modules.team_stance.team_strategy_for_stance) and
    # `declared_team_stance` (raw, for rationale-text framing only). These
    # used to be two separate storage reads (a GM Stance user_settings blob
    # and this Team Situation row); merging them into one row means one
    # fetch instead of two.
    declared_team_stance = _fetch_team_stance(
        config, user_id, str(user.get("_access_token") or ""), league_id
    )
    team_strategy = team_stance.team_strategy_for_stance(declared_team_stance)
    # Shares the exact same cached search Trade Hub's own endpoint uses
    # (trade_hub_engine.generate_trade_idea_records_cached) for this tile,
    # rather than letting compose_next_move_briefing recompute the identical
    # (league, roster, strategy, lens) search a user may have just triggered
    # moments earlier by opening Trade Hub.
    trade_idea_records = None
    trade_ideas_deferred = False
    if is_external:
        # Trade Hub needs Sleeper-only pick ownership: no idea search, no trade row.
        trade_idea_records = []
    elif league_calendar.trade_deadline_passed(league):
        # Past the trade deadline: no Top Trade Opportunity tile — an empty
        # (not None) list keeps compose_next_move_briefing from regenerating.
        trade_idea_records = []
    elif defer_trade_ideas:
        # Progressive first paint: skip the search (and the GM Targets read
        # that only feeds it); the client re-asks without this flag.
        trade_idea_records = []
        trade_ideas_deferred = True
    else:
        gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
            config, user_id, str(user.get("_access_token") or ""), league_id
        )
        try:
            trade_idea_records = trade_hub_engine.generate_trade_idea_records_cached(
                league_id=league_id,
                roster_id=int(my_roster.get("roster_id")),
                strategy=team_strategy,
                lens=lens,
                players_db_path=PLAYERS_DB_PATH,
                untouchable_player_ids=gm_untouchable_ids,
                gm_target_player_ids=gm_target_ids,
                team_stance=declared_team_stance,
                keeper_round_penalty=_trade_idea_keeper_round_penalty(user, league_id),
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
    injury_context = trade_analyzer_fit.roster_injury_context(
        roster_df, lineup_df, taxi_player_ids=my_roster.get("taxi")
    )

    # Moved ahead of compose_next_move_briefing below (this used to run
    # AFTER it, purely for this endpoint's own Team Snapshot power/
    # franchise rank fields) so build_strategy_check_tile's auto_strategy/
    # auto_strategy_label inputs are free — the exact same already-cached
    # rankings_frame row this endpoint already needed for Team Snapshot,
    # read once.
    power_rank = None
    power_rank_tied = False
    franchise_rank = None
    franchise_rank_tied = False
    starter_rank = None
    starter_rank_tied = False
    bench_rank = None
    bench_rank_tied = False
    auto_strategy = ""
    auto_strategy_label = ""
    rankings_frame = league_rankings.build_league_rankings_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if not rankings_frame.empty:
        my_roster_id = str(my_roster.get("roster_id") or "")
        match = rankings_frame[rankings_frame["roster_id"].astype(str) == my_roster_id]
        if not match.empty:
            power_rank = _clean_json_value(match.iloc[0].get("power_rank"))
            power_rank_tied = bool(match.iloc[0].get("power_rank_tied"))
            franchise_rank = _clean_json_value(match.iloc[0].get("franchise_rank"))
            franchise_rank_tied = bool(match.iloc[0].get("franchise_rank_tied"))
            # Starter/Bench Strength (web's Team Snapshot tiles 4-5) — same
            # rankings_frame already computes both columns (see
            # modules.league_rankings, shared with GET .../team-rankings'
            # identical starter_rank/bench_rank projection); reading them
            # here is free, no second engine call.
            starter_rank = _clean_json_value(match.iloc[0].get("starter_rank"))
            starter_rank_tied = bool(match.iloc[0].get("starter_rank_tied"))
            bench_rank = _clean_json_value(match.iloc[0].get("bench_rank"))
            bench_rank_tied = bool(match.iloc[0].get("bench_rank_tied"))
            auto_strategy = _clean_json_value(match.iloc[0].get("strategy")) or ""
            auto_strategy_label = _clean_json_value(match.iloc[0].get("strategy_label")) or ""

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
        team_stance=declared_team_stance,
        roster_record=my_roster.get("settings"),
        auto_strategy=auto_strategy,
        auto_strategy_label=auto_strategy_label,
        season_progress=record_signal.season_progress_fraction(league),
        include_trade_and_waiver=not is_external,
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
        "power_rank_tied": power_rank_tied,
        "franchise_rank": franchise_rank,
        "franchise_rank_tied": franchise_rank_tied,
        "starter_rank": starter_rank,
        "starter_rank_tied": starter_rank_tied,
        "bench_rank": bench_rank,
        "bench_rank_tied": bench_rank_tied,
    }

    # Free-tier cap matches the web app's own gate (app.py:
    # `visible_action_items = action_center_items if is_premium else
    # action_center_items[:4]`) — applied here to the already-composed,
    # priority-ordered Today's Game Plan list rather than the pre-
    # reorganization raw tile list web slices, since that's the exact
    # sequence this response actually displays.
    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)
    all_items = list(briefing.items)
    visible_items = all_items if is_premium else all_items[:FREE_DASHBOARD_VISIBLE_ITEMS]
    if not is_premium:
        # The Top Trade Opportunity tile is a trade idea like any other: a
        # Free caller only sees it if that idea fits in (or is already part
        # of) the ONE shared per-user pool Trade Hub / All Trades draw from,
        # so Dashboard + Trade Hub + switching lens can't each hand out
        # their own free idea.
        headline_records = trade_hub_presentation.order_trade_hub_visible_ideas(list(trade_idea_records or []))
        headline_id = trade_hub_presentation.idea_recommendation_id(headline_records[0]) if headline_records else ""
        _applied, pool_cap = _free_trade_idea_cap(user_id)
        trade_tile_allowed = bool(headline_id) and headline_id in free_tier_ledger.claim_trade_ideas(
            user_id, [headline_id], pool_cap
        )
        if not trade_tile_allowed:
            visible_items = [item for item in visible_items if not _is_trade_briefing_item(item)]

    projected_items = [_project_briefing_item(item) for item in visible_items]
    response = {
        "ok": True,
        "items": projected_items,
        "quiet": briefing.quiet,
        "quiet_reason": briefing.quiet_reason,
        "team_snapshot": team_snapshot,
        "reason": "",
        "entitlement": {
            "is_premium": is_premium,
            "visible_count": len(visible_items),
            "hidden_count": len(all_items) - len(visible_items),
            # Sent so clients can say "Free shows N" without a copy of N.
            "free_limit": FREE_DASHBOARD_VISIBLE_ITEMS,
        },
        # Additive. Built only from data computed above; see modules.this_week.
        "this_week": _dashboard_this_week(
            league=league,
            my_roster=my_roster,
            roster_df=roster_df,
            items=projected_items,
            # Deferred pass: the search has not run, so there is no "Hold"
            # verdict to give. None = omit the trade row; the full pass fills it.
            trade_idea_records=None if (trade_ideas_deferred or is_external) else trade_idea_records,
            stance=declared_team_stance,
        ),
    }
    # Additive: lets the Dashboard's "what matters now" strip show the real
    # trade-deadline week (modules.league_calendar), never a guessed date.
    response["trade_window"] = league_calendar.trade_window(league)
    # Additive: the effective strategy (declared Team Situation, else retool)
    # so the deadline card can frame buy vs sell without a second request.
    response["team_strategy"] = team_strategy
    if trade_ideas_deferred:
        response["trade_ideas_deferred"] = True
    if is_external:
        response["platform_notice"] = (
            f"Waiver and trade suggestions aren't available for {external_leagues.label_for(league_id)} "
            "leagues yet, so this page only shows what your imported roster can support."
        )
    return response


def _external_week_state(league_id: str, league: dict[str, Any]) -> dict[str, Any] | None:
    """The platform's current-week state for an imported league, or None.

    None when the platform can't be read or the league's season is not the NFL
    season we have schedules, stats and projections for (an older imported
    season has no "this week" to speak of)."""

    try:
        season = int(league.get("season") or 0)
        if not season or season != sleeper.default_player_stats_season():
            return None
        state = external_matchups.week_state(league_id)
        return state if state and int(state.get("week") or 0) > 0 else None
    except Exception:
        return None


def _external_dashboard_context(
    league_id: str, league: dict[str, Any], my_roster: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """League + roster for the Dashboard of an imported league.

    Adds the platform's current week (`settings.leg`) and, when every starter
    maps to a FantasyDesk player, this team's real starters, which is what the
    "lineup check" row reads. A lineup with an unmapped starter is left out
    entirely: the row would otherwise claim a lineup is set that we only half
    know. Never raises."""

    state = _external_week_state(league_id, league)
    if state is None:
        return league, my_roster
    league = {**league, "settings": {**(league.get("settings") or {}), "leg": int(state["week"])}}
    try:
        lineup = external_matchups.lineup_for(league_id, int(my_roster.get("roster_id")), state)
    except Exception:
        lineup = None
    if lineup and lineup["starters"] and not lineup["unmapped"]:
        my_roster = {**my_roster, "starters": list(lineup["starters"]) + ["0"] * len(lineup["empty_slots"])}
    return league, my_roster


def _dashboard_this_week(
    *,
    league: dict[str, Any],
    my_roster: dict[str, Any],
    roster_df: pd.DataFrame,
    items: list[dict[str, Any]],
    trade_idea_records: list[Any] | None,
    stance: str,
) -> dict[str, Any] | None:
    """The Dashboard's "This week" strip. Never raises: a failure here must not
    take the whole Dashboard down, so it just omits the strip."""

    try:
        roster_rows: dict[str, dict[str, Any]] = {}
        bye_ids: set[str] = set()
        if league_calendar.is_in_season(league) and not roster_df.empty:
            week = league_calendar.current_league_week(league) or 0
            games = None
            season = 0
            if week:
                try:
                    season = int(league.get("season") or 0) or sleeper.default_player_stats_season()
                    games = nfl_schedule.load_games()
                except Exception:
                    games = None
            for _, row in roster_df.iterrows():
                player_id = str(row.get("player_id") or "")
                if not player_id:
                    continue
                roster_rows[player_id] = {
                    "name": row.get("name"),
                    "position": row.get("position"),
                    "status": row.get("status"),
                    "injury_status": row.get("injury_status"),
                }
                team = str(row.get("team") or "").strip().upper()
                if games is not None and team and week:
                    matchup = nfl_schedule.team_matchup_for_week(team, week, season, games=games)
                    if matchup is not None and matchup.get("bye"):
                        bye_ids.add(player_id)
        return this_week.build_this_week(
            league=league,
            roster=my_roster,
            roster_rows=roster_rows,
            bye_player_ids=bye_ids,
            items=items,
            trade_records=trade_idea_records,
            stance=stance,
        )
    except Exception:
        return None


# Bounds the per-request fan-out in get_portfolio below — plenty for
# modules.saved_leagues' real-world Premium usage (a handful of leagues)
# without one request opening unboundedly many threads if an account has
# saved dozens.
_PORTFOLIO_FANOUT_MAX_WORKERS = 8

# A single per-league row makes up to 3 sequential calls (team_stance,
# GM Targets, dashboard_engine.build_league_summary's own Sleeper/rankings
# work), each individually bounded at 15s (this file's established
# requests.get timeout convention) — 25s gives real, slow-but-working rows
# room to finish while still bounding the whole fan-out well under a
# typical client/proxy timeout, instead of the old unbounded wait.
_PORTFOLIO_FANOUT_TIMEOUT_SECONDS = 25

_PORTFOLIO_UPSELL = {
    "title": "See every league at a glance",
    "body": (
        "Portfolio is a Premium feature — free accounts keep one saved league, "
        "so there's nothing to aggregate yet. Upgrade to Premium to save every "
        "league you're in and see your record, rank, and top need or "
        "opportunity across all of them in one place."
    ),
}

# GM Plan and Trade Finder are both Premium-only on app.py (see
# render_gm_plan... and modules/trade_hub_presentation.py's current_user_is_premium()
# gates), but shipped fully free/ungated on this API — coridian_, 2026-10-17:
# "streamlit had proper premium bqarriers" (confirming these should match).
_GM_PLAN_UPSELL = {
    "title": "Your season-arc roadmap",
    "body": (
        "GM Plan is a Premium feature: where you stand, your best trade "
        "paths, and your roster construction — framed by your declared "
        "Team Situation. Upgrade to Premium to unlock it."
    ),
}
_TRADE_FINDER_UPSELL = {
    "title": "Build and search for a trade",
    "body": (
        "Trade Finder is a Premium feature — build a custom package and "
        "search every roster in your league for a real match. Upgrade to "
        "Premium to unlock it."
    ),
}

# coridian_, 2026-10-18: "Live draft needs to be locked." Same shape as
# _TRADE_FINDER_UPSELL above — neither Live Draft's own Sleeper reference
# nor Streamlit's modules.live_draft_ui had a premium gate before this; a
# new product decision, not catching a missed parity gap.
_LIVE_DRAFT_UPSELL = {
    "title": "Draft with real-time recommendations",
    "body": (
        "Live Draft is a Premium feature — Best Available/Best Fit picks, "
        "a live roster-strength board, and positional-run alerts while "
        "your draft is actually happening. Upgrade to Premium to unlock it."
    ),
}


def _build_portfolio_row(
    config: dict,
    user_id: str,
    access_token: str,
    lens: str,
    sleeper_username: str,
    entitlement: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    """One saved league's Portfolio row — runs on a worker thread.

    Fans out the exact same three per-league calls the old sequential loop
    made (team_stance, GM Targets, dashboard_engine.build_league_summary) so
    a caller with several saved leagues pays the slowest ONE of them
    instead of the sum of all of them. Safe to run concurrently: `config`/
    `user_id`/`access_token` are read-only here, `_fetch_team_stance` /
    `_fetch_gm_target_player_ids` each make their own `requests.get` call
    (no shared Session object to race), and dashboard_engine.build_league_summary's
    own Sleeper/rankings caches are already keyed per league_id and guarded
    with their own locks (modules.sleeper's `_players_memo_lock`,
    modules.rankings' `_PROCESS_BUILD_LOCKS`) for exactly this kind of
    concurrent multi-league access.
    """

    league_id = saved_leagues.normalize_league_id(row.get("league_id"))
    if not league_id:
        return {"status": "skip"}
    league_name = str(row.get("league_name") or "").strip() or league_id
    if external_leagues.is_external_league_key(league_id):
        # Portfolio's Next Move briefing is the Dashboard engine, which ESPN
        # leagues can't feed yet (see modules.espn_leagues).
        return {
            "status": "failed",
            "league_id": league_id,
            "league_name": league_name,
            "reason": espn_leagues.ESPN_NOT_AVAILABLE_REASON,
        }
    # Same fix as _resolve_my_roster: this row's OWN sleeper_username
    # (captured when this specific league was saved) over the account-wide
    # `sleeper_username` param, which only reflects whichever Sleeper
    # account was linked most recently — real repro, coridian_: linking a
    # second Sleeper username for a new league silently broke every other
    # saved league in Portfolio that was linked under the first one, even
    # though the right username was sitting right here on each row.
    row_sleeper_username = str(row.get("sleeper_username") or "") or sleeper_username

    try:
        # The two Supabase reads are independent -- overlap them so a cold
        # row pays one round trip instead of two back to back.
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="dgm-portfolio-gm-targets"
        ) as side_executor:
            gm_targets_future = side_executor.submit(
                _fetch_gm_target_player_ids, config, user_id, access_token, league_id
            )
            team_stance_value = _fetch_team_stance(config, user_id, access_token, league_id)
            gm_target_ids, gm_untouchable_ids = gm_targets_future.result()
        summary = dashboard_engine.build_league_summary(
            league_id=league_id,
            lens=lens,
            sleeper_username=row_sleeper_username,
            players_db_path=PLAYERS_DB_PATH,
            team_stance_value=team_stance_value,
            gm_target_player_ids=gm_target_ids,
            gm_untouchable_player_ids=gm_untouchable_ids,
            entitlement=entitlement,
        )
    except Exception:
        return {
            "status": "failed",
            "league_id": league_id,
            "league_name": league_name,
            "reason": "unavailable",
        }

    if not summary.get("ok"):
        reason = summary.get("reason") or "unavailable"
        if reason not in dashboard_engine.LEAGUE_SUMMARY_SKIP_REASONS:
            reason = "unavailable"
        return {
            "status": "failed",
            "league_id": league_id,
            "league_name": league_name,
            "reason": reason,
        }

    return {
        "status": "ok",
        "league_id": league_id,
        "league_name": league_name,
        "summary": summary,
    }


def _portfolio_context(lens: str, user: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Shared front half of every Portfolio route: lens validation, the
    Premium gate, and the caller's (rollover-resolved) saved leagues.

    Returns `(early_response, context)`. `early_response` is the complete
    response body for every case that has no per-league work to do (Free
    upsell, no user id, saved leagues unreadable) and `None` otherwise, in
    which case `context` carries what the per-league builders need. Kept in
    one place so GET /v1/portfolio, GET /v1/portfolio/leagues and GET
    /v1/portfolio/leagues/{league_id} can never disagree about who gets
    Portfolio or which leagues it covers.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    if not user_id:
        profile: dict[str, str] = {}
        saved_rows_future = None
    else:
        # The saved-leagues read (plus its rollover check) doesn't depend on
        # the profile, so start it alongside the profile read instead of
        # after it -- one fewer serial Supabase round trip ahead of the
        # per-league work. A Free caller's result is simply discarded.
        prefetch_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="dgm-portfolio-saved-leagues"
        )
        saved_rows_future = prefetch_executor.submit(
            _fetch_saved_leagues_cached, config, access_token, user_id
        )
        prefetch_executor.shutdown(wait=False)
        profile = _fetch_profile_fields(config, user_id, access_token)
    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)

    if not is_premium:
        return {
            "ok": True,
            "is_premium": False,
            "lens": lens,
            "leagues": [],
            "failed_leagues": [],
            "upsell": _PORTFOLIO_UPSELL,
        }, {}

    if not user_id or saved_rows_future is None:
        return {"ok": True, "is_premium": True, "lens": lens, "leagues": [], "failed_leagues": [], "upsell": None}, {}

    try:
        saved_rows, error = saved_rows_future.result()
    except Exception:
        saved_rows, error = [], "saved_leagues_unavailable"
    if error:
        return {
            "ok": True,
            "is_premium": True,
            "lens": lens,
            "leagues": [],
            "failed_leagues": [],
            "upsell": None,
            "reason": "saved_leagues_unavailable",
        }, {}

    return None, {
        "config": config,
        "user_id": user_id,
        "access_token": access_token,
        "saved_rows": saved_rows or [],
        "sleeper_username": str(profile.get("sleeper_username") or ""),
        "entitlement": str(profile.get("entitlement") or "free"),
    }


def _project_portfolio_league(result: dict[str, Any]) -> dict[str, Any]:
    """One successful `_build_portfolio_row` result -> its response row."""

    summary = result["summary"]
    top_item = summary.get("top_item")
    # `top_items` is the same already-ranked/deduped signal list `top_item`
    # draws its first entry from (modules.dashboard_engine.build_league_summary),
    # just not truncated to one — a saved league's quick-glance card wants
    # a few short lines (value trending down / injury / news story /
    # waiver info), not only the single highest-priority headline. Falls
    # back to a one-item list built from `top_item` for any caller whose
    # `summary` predates this field, so nothing regresses to an empty list.
    top_items = summary.get("top_items")
    if top_items is None:
        top_items = [top_item] if top_item else []
    return {
        "league_id": result["league_id"],
        "league_name": result["league_name"],
        "team_name": summary.get("team_name") or "",
        "team_avatar_url": summary.get("team_avatar_url") or "",
        "wins": _clean_json_value(summary.get("wins")),
        "losses": _clean_json_value(summary.get("losses")),
        "ties": _clean_json_value(summary.get("ties")),
        "health_flag": summary.get("health_flag"),
        "power_rank": _clean_json_value(summary.get("power_rank")),
        "power_rank_tied": bool(summary.get("power_rank_tied")),
        "franchise_rank": _clean_json_value(summary.get("franchise_rank")),
        "franchise_rank_tied": bool(summary.get("franchise_rank_tied")),
        "roster_value_rank": _clean_json_value(summary.get("roster_value_rank")),
        "roster_value_rank_tied": bool(summary.get("roster_value_rank_tied")),
        "archetype": _clean_json_value(summary.get("archetype")),
        "archetype_label": _clean_json_value(summary.get("archetype_label")),
        "top_asset": _project_portfolio_top_asset(summary.get("top_asset")),
        "top_item": _project_briefing_item_payload(top_item) if top_item else None,
        "top_items": [_project_briefing_item_payload(item) for item in top_items if item],
    }


def _portfolio_saved_league_stub(row: dict[str, Any]) -> dict[str, str] | None:
    league_id = saved_leagues.normalize_league_id(row.get("league_id"))
    if not league_id:
        return None
    return {"league_id": league_id, "league_name": str(row.get("league_name") or "").strip() or league_id}


@app.get("/v1/portfolio/leagues")
def get_portfolio_leagues(lens: str = "Dynasty", user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Portfolio's cheap index: the Premium gate plus the caller's saved
    leagues (id + name, already rollover-resolved), with NO per-league
    valuation work.

    Portfolio perf audit, 2026-10-21: GET /v1/portfolio answers in one
    response only after EVERY saved league's summary is built, and those
    builds are CPU-bound pandas work that shares one Python process (one
    GIL) — a real 5-league account measured ~3.7s of mostly serialized
    engine time even after the backend fixes in the same change. Clients
    that call this index first and then GET /v1/portfolio/leagues/{id} for
    each league concurrently (a) paint each league card as soon as its own
    summary is ready and (b) let those per-league requests spread across
    the mobile-api worker processes instead of queueing behind one GIL.
    GET /v1/portfolio stays as-is for already-shipped app builds.
    """

    early_response, context = _portfolio_context(lens, user)
    if early_response is not None:
        return {**early_response, "saved_leagues": []}
    saved_league_stubs = []
    for row in context["saved_rows"]:
        stub = _portfolio_saved_league_stub(row) if isinstance(row, dict) else None
        if stub is not None:
            saved_league_stubs.append(stub)
    return {
        "ok": True,
        "is_premium": True,
        "lens": lens,
        "saved_leagues": saved_league_stubs,
        "leagues": [],
        "failed_leagues": [],
        "upsell": None,
    }


@app.get("/v1/portfolio/leagues/{league_id}")
def get_portfolio_league(
    league_id: str,
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """One saved league's Portfolio row — exactly the row GET /v1/portfolio
    would return for it (same `_build_portfolio_row` + projection, same
    Premium gate, same failure reasons), for clients loading Portfolio
    progressively (see GET /v1/portfolio/leagues).

    `league_id` must be one of the caller's own saved leagues (as listed by
    the index); anything else is a 404 rather than a summary for a league
    the caller never saved. Exactly one of `league` / `failed_league` is
    set on a Premium response."""

    early_response, context = _portfolio_context(lens, user)
    if early_response is not None:
        return {**early_response, "league": None, "failed_league": None}

    normalized_league_id = saved_leagues.normalize_league_id(league_id)
    row = next(
        (
            saved_row
            for saved_row in context["saved_rows"]
            if isinstance(saved_row, dict)
            and normalized_league_id
            and saved_leagues.normalize_league_id(saved_row.get("league_id")) == normalized_league_id
        ),
        None,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="That league is not one of your saved leagues.")

    stub = _portfolio_saved_league_stub(row) or {"league_id": normalized_league_id, "league_name": normalized_league_id}
    # Same per-league deadline GET /v1/portfolio applies to each row, for
    # the same reason (one hung Sleeper call must surface as a timed-out
    # league, not an endless spinner).
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="dgm-portfolio-league")
    try:
        future = executor.submit(
            _build_portfolio_row,
            context["config"],
            context["user_id"],
            context["access_token"],
            lens,
            context["sleeper_username"],
            context["entitlement"],
            row,
        )
        try:
            result = future.result(timeout=_PORTFOLIO_FANOUT_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            result = {"status": "failed", **stub, "reason": "timed_out"}
        except Exception:
            result = {"status": "failed", **stub, "reason": "unavailable"}
    finally:
        executor.shutdown(wait=False)

    league_payload = None
    failed_league = None
    if result.get("status") == "ok":
        league_payload = _project_portfolio_league(result)
    else:
        failed_league = {
            "league_id": result.get("league_id") or stub["league_id"],
            "league_name": result.get("league_name") or stub["league_name"],
            "reason": result.get("reason") or "unavailable",
        }
    return {
        "ok": True,
        "is_premium": True,
        "lens": lens,
        "league": league_payload,
        "failed_league": failed_league,
        "upsell": None,
    }


_PORTFOLIO_EXPOSURE_UPSELL = {
    "title": "See your player exposure",
    "body": (
        "Exposure is a Pro feature: which players you own across every league, "
        "how much of your portfolio value rides on a few of them, and your "
        "position mix. Upgrade to Pro to unlock it."
    ),
}


@app.get("/v1/portfolio/exposure")
def get_portfolio_exposure(lens: str = "Dynasty", user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Cross-league player exposure (Pro). "You own Bijan Robinson in 3 of 5 leagues."

    Product decision (owner): this is a Pro feature. `premium.has_cross_league_exposure`
    was defined at Front Office tier but never called by any feature, and Front
    Office is no longer sold; the Pro gate here overrides it.

    The entitlement gate runs first: a Free caller gets only the upsell, with no
    saved-league read, no Sleeper call and no valuation work. Per-league rosters
    and values come from the same cached building blocks Portfolio's league rows
    use (modules.portfolio_exposure). ESPN leagues are skipped (their rosters are
    not available to the valuation engines yet) and reported in `skipped_leagues`.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    profile = _fetch_profile_fields(config, user_id, access_token) if user_id else {}
    if not premium.has_cross_league_exposure(profile.get("entitlement")):
        return {
            "ok": True,
            "is_premium": False,
            "lens": lens,
            "exposure": None,
            "skipped_leagues": [],
            "upsell": _PORTFOLIO_EXPOSURE_UPSELL,
        }

    base = {"ok": True, "is_premium": True, "lens": lens, "upsell": None}
    saved_rows, error = _fetch_saved_leagues_cached(config, access_token, user_id) if user_id else ([], None)
    if error:
        return {**base, "exposure": None, "skipped_leagues": [], "reason": "saved_leagues_unavailable"}

    skipped: list[dict[str, Any]] = []
    targets: list[tuple[str, str, str]] = []
    default_username = str(profile.get("sleeper_username") or "")
    seen: set[str] = set()
    for row in saved_rows or []:
        league_id = saved_leagues.normalize_league_id(row.get("league_id"))
        if not league_id or league_id in seen:
            continue
        seen.add(league_id)
        league_name = str(row.get("league_name") or "").strip() or league_id
        if external_leagues.is_external_league_key(league_id):
            skipped.append(
                {"league_id": league_id, "league_name": league_name, "reason": espn_leagues.ESPN_NOT_AVAILABLE_REASON}
            )
            continue
        targets.append((league_id, league_name, str(row.get("sleeper_username") or "") or default_username))

    def _one(target: tuple[str, str, str]) -> dict[str, Any]:
        league_id, league_name, username = target
        return portfolio_exposure.build_league_ownership(
            league_id=league_id,
            league_name=league_name,
            lens=lens,
            sleeper_username=username,
            players_db_path=PLAYERS_DB_PATH,
        )

    results: list[dict[str, Any]] = []
    if targets:
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(targets), _PORTFOLIO_FANOUT_MAX_WORKERS), thread_name_prefix="dgm-portfolio-exposure"
        )
        try:
            futures = [executor.submit(_one, t) for t in targets]
            concurrent.futures.wait(futures, timeout=_PORTFOLIO_FANOUT_TIMEOUT_SECONDS)
            for (league_id, league_name, _), future in zip(targets, futures):
                reason = "timed_out"
                if future.done():
                    try:
                        result = future.result()
                    except Exception:
                        result = {"ok": False}
                        reason = "unavailable"
                    else:
                        reason = str(result.get("reason") or "unavailable")
                    if result.get("ok"):
                        results.append(result)
                        continue
                skipped.append({"league_id": league_id, "league_name": league_name, "reason": reason})
        finally:
            executor.shutdown(wait=False)

    exposure = portfolio_exposure.aggregate_exposure(results)
    return {**base, "exposure": exposure, "skipped_leagues": skipped}


@app.get("/v1/portfolio")
def get_portfolio(lens: str = "Dynasty", user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """Thin timing wrapper — see _get_portfolio_impl for the real endpoint.

    coridian_, 2026-10-19/20: real, repeatable "Portfolio takes 18+/10+/12s"
    reports that a live DYNASTYGM_PERF capture during an actual slow load
    could NOT explain — every individual sub-call (auth, Supabase, Sleeper)
    measured well under 500ms in that capture, yet the page still visibly
    took far longer to load than that. His own diagnosis: "add timing
    around the entire Portfolio request and its major stages, including
    queue/wait time. Existing timing entries don't account for the full
    wait." This one enclosing time_block is exactly that — a single
    "portfolio_total_request" entry spanning everything from the moment
    this function starts (after FastAPI/Starlette's own request routing
    and the require_user auth dependency have already run) to the moment
    it returns, so the NEXT DYNASTYGM_PERF capture can show whether the
    gap is inside this function's own Python-level work after all, or
    entirely upstream of it (a proxy layer, worker-queue wait time before
    this handler even started, or something client-side)."""

    with performance.time_block("portfolio_total_request", category="app"):
        return _get_portfolio_impl(lens, user)


def _get_portfolio_impl(lens: str, user: dict[str, Any]) -> dict[str, Any]:
    """Cross-league "Portfolio" — one compact row per saved league.

    coridian_-approved multi-league view: a single surface showing this
    user's standing/needs/opportunities across every connected league at
    once, previously discussed as a planned Premium feature but never
    built. Each row is built by modules.dashboard_engine.build_league_summary
    — the exact same engines (modules.league_value_settings,
    modules.trade_hub_engine, modules.league_rankings, modules.injury_ui,
    dashboard_engine.compose_next_move_briefing) GET
    /v1/leagues/{league_id}/dashboard already uses for a single league, just
    called once per saved league and condensed to the handful of fields a
    row needs — no new valuation or ranking math. The web app's Portfolio
    page (modules.portfolio_page) calls this exact same shared function, so
    both surfaces agree.

    Gated behind Premium the same way every other Premium feature resolves
    entitlement (profile.entitlement via _fetch_profile_fields — the single
    authoritative source every other gate in this file already uses). This
    is inherently a Premium-only surface: modules.saved_leagues caps Free
    accounts at exactly one saved league, so there is nothing to aggregate
    on Free — a Free caller gets an honest upsell instead of an empty or
    broken screen, never partial/truncated data (there's no "the rest is
    locked" partial state that makes sense for a one-league Free account).

    A league that fails to build its summary (Sleeper outage, a deleted
    league, a genuinely unexpected error) is reported in `failed_leagues`
    with a short reason instead of failing the whole response — one broken
    league never blanks the rest of the portfolio.
    """

    early_response, context = _portfolio_context(lens, user)
    if early_response is not None:
        return early_response
    config = context["config"]
    user_id = context["user_id"]
    access_token = context["access_token"]
    saved_rows = context["saved_rows"]
    sleeper_username = context["sleeper_username"]
    entitlement = context["entitlement"]
    leagues: list[dict[str, Any]] = []
    failed_leagues: list[dict[str, Any]] = []

    # Fan the per-league work out across a thread pool instead of paying
    # each saved league's Supabase + Sleeper round trips back to back.
    # Bounded by _PORTFOLIO_FANOUT_TIMEOUT_SECONDS overall (coridian_,
    # 2026-10-19: "timed out loading portfolio" — the old bare
    # `executor.map` had no bound at all, so one genuinely hung Sleeper
    # call for one saved league blocked the ENTIRE response forever rather
    # than just that one league's row, defeating this endpoint's own
    # "one broken league never blanks the rest" design intent). Futures are
    # submitted individually (not via executor.map) so a still-running one
    # past the deadline can be reported as a timed-out failure instead of
    # blocked on; `shutdown(wait=False)` below lets any such orphaned
    # thread finish on its own without holding this response open for it.
    results: list[dict[str, Any]] = []
    if saved_rows:
        worker = functools.partial(
            _build_portfolio_row, config, user_id, access_token, lens, sleeper_username, entitlement
        )
        max_workers = min(len(saved_rows), _PORTFOLIO_FANOUT_MAX_WORKERS)
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="dgm-portfolio-fanout"
        )
        try:
            futures = [executor.submit(worker, row) for row in saved_rows]
            concurrent.futures.wait(futures, timeout=_PORTFOLIO_FANOUT_TIMEOUT_SECONDS)
            for row, future in zip(saved_rows, futures):
                if future.done():
                    try:
                        results.append(future.result())
                    except Exception:
                        results.append(
                            {
                                "status": "failed",
                                "league_id": saved_leagues.normalize_league_id(row.get("league_id")) or "",
                                "league_name": str(row.get("league_name") or "").strip()
                                or str(row.get("league_id") or ""),
                                "reason": "unavailable",
                            }
                        )
                else:
                    results.append(
                        {
                            "status": "failed",
                            "league_id": saved_leagues.normalize_league_id(row.get("league_id")) or "",
                            "league_name": str(row.get("league_name") or "").strip()
                            or str(row.get("league_id") or ""),
                            "reason": "timed_out",
                        }
                    )
        finally:
            executor.shutdown(wait=False)

    for result in results:
        status = result["status"]
        if status == "skip":
            continue
        if status == "failed":
            failed_leagues.append(
                {
                    "league_id": result["league_id"],
                    "league_name": result["league_name"],
                    "reason": result["reason"],
                }
            )
            continue

        leagues.append(_project_portfolio_league(result))

    return {
        "ok": True,
        "is_premium": True,
        "lens": lens,
        "leagues": leagues,
        "failed_leagues": failed_leagues,
        "upsell": None,
    }


# --- All leagues at a glance ---------------------------------------------
#
# Short TTL on purpose: these cards summarize live-ish state (waiver pool,
# record, news), so a few minutes of staleness is fine for a glance view but
# anything longer would start showing a player who was already claimed.
# Pull-to-refresh on the client re-reads within the same window; the full
# single-league screens each card links into are always live.
LEAGUE_GLANCE_TTL_SECONDS = 180

# Same bug class as _PORTFOLIO_FANOUT_TIMEOUT_SECONDS above, found during a
# 2026-10-19 performance audit: this endpoint's fan-out used a bare
# `executor.map`, which has no overall bound, so one genuinely hung
# per-league call (Sleeper never responding, or a stuck Redis single-flight
# lock) blocks the ENTIRE leagues-glance response forever instead of just
# that one league's row -- directly contradicting this endpoint's own
# docstring promise that "one failing league is reported in failed_leagues
# instead of blanking the response." Each per-league row makes up to 3
# sequential calls (team_stance, GM Targets, league_glance.build_league_glance's
# own Sleeper/dashboard work), each individually bounded at 15s (this file's
# established requests.get timeout convention); 25s mirrors Portfolio's own
# deadline and gives real, slow-but-working rows room to finish.
_LEAGUE_GLANCE_FANOUT_TIMEOUT_SECONDS = 25

_LEAGUE_GLANCE_UPSELL = {
    "title": "All your leagues at a glance",
    "body": (
        "Premium keeps every league you're in and shows each one's record, top "
        "waiver add, top trade idea, news, and biggest need side by side."
    ),
}


def _league_glance_cache_key(user_id: str, league_id: str, lens: str) -> str:
    return redis_cache.build_cache_key("league_glance", user_id, league_id, lens, PLAYERS_DB_PATH)


def _build_league_glance_row(
    config: dict,
    user_id: str,
    access_token: str,
    lens: str,
    sleeper_username: str,
    news_pool_loader: Any,
    row: dict[str, Any],
) -> dict[str, Any]:
    """One saved league's glance card, through a short-TTL Redis cache.

    The whole per-league compute (including the Team Situation / GM Targets
    reads) sits inside the cache, so a repeat visit inside the TTL costs one
    Redis GET per league. redis_single_flight_cache fails open (computes
    directly) if Redis is down, and never caches an exception, so a league
    that blew up is retried on the next visit instead of pinned as broken.
    """

    league_id = saved_leagues.normalize_league_id(row.get("league_id"))
    if not league_id:
        return {"status": "skip"}
    league_name = str(row.get("league_name") or "").strip() or league_id
    if external_leagues.is_external_league_key(league_id):
        return {
            "status": "failed",
            "league_id": league_id,
            "league_name": league_name,
            "reason": espn_leagues.ESPN_NOT_AVAILABLE_REASON,
        }
    # Same fix as _resolve_my_roster/_build_portfolio_row: this row's OWN
    # sleeper_username (captured when this specific league was saved) over
    # the account-wide `sleeper_username` param, which only reflects
    # whichever Sleeper account was linked most recently.
    row_sleeper_username = str(row.get("sleeper_username") or "") or sleeper_username

    def _compute() -> dict[str, Any]:
        team_stance_value = _fetch_team_stance(config, user_id, access_token, league_id)
        gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
            config, user_id, access_token, league_id
        )
        return league_glance.build_league_glance(
            league_id=league_id,
            lens=lens,
            sleeper_username=row_sleeper_username,
            players_db_path=PLAYERS_DB_PATH,
            news_pool=news_pool_loader(),
            team_stance_value=team_stance_value,
            gm_target_player_ids=gm_target_ids,
            gm_untouchable_player_ids=gm_untouchable_ids,
        )

    try:
        glance = redis_cache.redis_single_flight_cache(
            cache_key=_league_glance_cache_key(user_id, league_id, lens),
            ttl_seconds=LEAGUE_GLANCE_TTL_SECONDS,
            compute=_compute,
        )
    except Exception:
        return {"status": "failed", "league_id": league_id, "league_name": league_name, "reason": "unavailable"}

    if not glance.get("ok"):
        reason = glance.get("reason") or "unavailable"
        if reason not in dashboard_engine.LEAGUE_SUMMARY_SKIP_REASONS:
            reason = "unavailable"
        return {"status": "failed", "league_id": league_id, "league_name": league_name, "reason": reason}

    return {"status": "ok", "league_id": league_id, "league_name": league_name, "glance": glance}


def _project_league_glance(league_id: str, league_name: str, glance: dict[str, Any]) -> dict[str, Any]:
    def _clean_mapping(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        return {key: _clean_json_value(item) for key, item in value.items()}

    news = _clean_mapping(glance.get("news")) or {"news_count": 0, "injury_count": 0}
    return {
        "league_id": league_id,
        "league_name": league_name,
        "team_name": glance.get("team_name") or "",
        "record": _clean_mapping(glance.get("record")),
        "waiver": _clean_mapping(glance.get("waiver")),
        "trade": _clean_mapping(glance.get("trade")),
        "news": news,
        "need": _clean_mapping(glance.get("need")),
    }


@app.get("/v1/leagues-glance")
def get_leagues_glance(lens: str = "Dynasty", user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    """"All leagues at a glance": one compact card per saved league.

    Each card carries only five trimmed data points (record, top waiver add,
    top trade idea headline, roster news/injury count, top team need), built
    by modules.league_glance from the same engines the single-league
    Dashboard / Waivers / Trade Hub / Alerts / My Team endpoints use. It is
    a separate, lighter endpoint from GET /v1/portfolio (which runs the full
    Next Move briefing per league) and does not touch the Dashboard
    endpoint's behavior.

    Premium-only by construction: modules.saved_leagues caps Free accounts
    at one saved league, so there is nothing to compare. Free callers get an
    upsell payload (the client renders a locked teaser) and no per-league
    work runs. Entitlement resolves exactly like every other gate in this
    file (profile.entitlement via _fetch_profile_fields).

    Per-league results are cached in Redis for LEAGUE_GLANCE_TTL_SECONDS
    and fanned out over a bounded thread pool, bounded overall by
    _LEAGUE_GLANCE_FANOUT_TIMEOUT_SECONDS; one failing (or timed-out)
    league is reported in `failed_leagues` instead of blanking the
    response.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    profile = _fetch_profile_fields(config, user_id, access_token) if user_id else {}
    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)

    base = {
        "ok": True,
        "is_premium": is_premium,
        "lens": lens,
        "leagues": [],
        "failed_leagues": [],
        "upsell": None,
        "cache_ttl_seconds": LEAGUE_GLANCE_TTL_SECONDS,
    }
    if not is_premium:
        return {**base, "upsell": _LEAGUE_GLANCE_UPSELL}
    if not user_id:
        return base

    saved_rows, error = _fetch_saved_leagues_cached(config, access_token, user_id)
    if error:
        return {**base, "reason": "saved_leagues_unavailable"}

    # The news pool is a disk read shared by every league: load it at most
    # once per request, and only if some league actually misses the cache.
    news_lock = threading.Lock()
    news_holder: dict[str, Any] = {}

    def _news_pool_loader() -> Any:
        with news_lock:
            if "pool" not in news_holder:
                news_cache.schedule_news_cache_refresh()
                news_holder["pool"] = news_cache.load_cached_news_pool()
            return news_holder["pool"]

    sleeper_username = str(profile.get("sleeper_username") or "")
    results: list[dict[str, Any]] = []
    if saved_rows:
        worker = functools.partial(
            _build_league_glance_row, config, user_id, access_token, lens, sleeper_username, _news_pool_loader
        )
        max_workers = min(len(saved_rows), _PORTFOLIO_FANOUT_MAX_WORKERS)
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="dgm-glance-fanout"
        )
        # Futures submitted individually (not via executor.map) so a still-
        # running one past the deadline can be reported as a timed-out
        # failure instead of blocked on; `shutdown(wait=False)` lets any
        # such orphaned thread finish on its own without holding this
        # response open for it. See _LEAGUE_GLANCE_FANOUT_TIMEOUT_SECONDS.
        try:
            futures = [executor.submit(worker, row) for row in saved_rows]
            concurrent.futures.wait(futures, timeout=_LEAGUE_GLANCE_FANOUT_TIMEOUT_SECONDS)
            for row, future in zip(saved_rows, futures):
                if future.done():
                    try:
                        results.append(future.result())
                    except Exception:
                        results.append(
                            {
                                "status": "failed",
                                "league_id": saved_leagues.normalize_league_id(row.get("league_id")) or "",
                                "league_name": str(row.get("league_name") or "").strip()
                                or str(row.get("league_id") or ""),
                                "reason": "unavailable",
                            }
                        )
                else:
                    results.append(
                        {
                            "status": "failed",
                            "league_id": saved_leagues.normalize_league_id(row.get("league_id")) or "",
                            "league_name": str(row.get("league_name") or "").strip()
                            or str(row.get("league_id") or ""),
                            "reason": "timed_out",
                        }
                    )
        finally:
            executor.shutdown(wait=False)

    leagues: list[dict[str, Any]] = []
    failed_leagues: list[dict[str, Any]] = []
    for result in results:
        if result["status"] == "skip":
            continue
        if result["status"] == "failed":
            failed_leagues.append(
                {"league_id": result["league_id"], "league_name": result["league_name"], "reason": result["reason"]}
            )
            continue
        leagues.append(_project_league_glance(result["league_id"], result["league_name"], result["glance"]))

    return {**base, "leagues": leagues, "failed_leagues": failed_leagues}


@app.get("/v1/leagues/{league_id}/gm-plan")
def get_gm_plan(
    league_id: str = Depends(resolve_league_path_id),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """A season-phase-aware roadmap, conditioned on the caller's declared
    Team Situation stance (modules.team_stance — Rebuilding / Competing /
    Balanced; NOT the older, valuation-affecting "GM Stance" team-strategy
    system at /v1/leagues/{league_id}/gm-stance, which this endpoint never
    reads for framing purposes beyond the pass-through `strategy` argument
    the shared trade-idea search already requires).

    A season-arc complement to the Dashboard's one-off "Next Move" tile
    (get_league_dashboard) — not a replacement for it. Purely additive
    aggregation: every module.gm_plan.build_gm_plan input below is an
    ALREADY-COMPUTED output of an existing engine
    (modules.league_rankings.build_league_rankings_frame_cached for
    power/draft-capital/roster-construction ranks,
    modules.trade_hub_engine.generate_trade_idea_records_cached for trade
    ideas — the same stance-framed records the Dashboard's trade tile
    uses). No new valuation math is introduced here.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    profile = _fetch_profile_fields(config, user_id, access_token) if user_id else {}

    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return {"ok": True, "quiet": True, "focus_areas": [], "reason": reason, "is_premium": False, "upsell": None}

    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)
    if not is_premium:
        return {
            "ok": True,
            "quiet": True,
            "focus_areas": [],
            "reason": "",
            "is_premium": False,
            "upsell": _GM_PLAN_UPSELL,
        }

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    # Same "leg"/"week" field modules.league_standings already reads off
    # Sleeper's raw league settings — reused, not recomputed.
    raw_settings = league.get("settings") or {}
    current_week = raw_settings.get("leg") or raw_settings.get("week")
    playoff_week_start = raw_settings.get("playoff_week_start")
    # Sleeper's real settings.trade_deadline drives the deadline phase
    # (modules.league_calendar), not the old hardcoded weeks 4-11.
    trade_window = league_calendar.trade_window(league)
    season_phase = gm_plan.derive_season_phase(
        current_week,
        playoff_week_start,
        league_calendar.trade_deadline_week(league) if league_calendar.is_in_season(league) else None,
    )

    declared_team_stance = _fetch_team_stance(config, user_id, access_token, league_id)

    my_roster_id = str(my_roster.get("roster_id") or "")

    # Connectivity-audit fix: GM Plan was the only roster-facing screen that
    # built its roadmap with zero awareness of the team's own injuries, even
    # though get_league_dashboard and get_league_waivers already compute this
    # exact same roster_injury_context for this same user's roster — same
    # settings/valued/roster_df/lineup_df pattern as get_league_dashboard
    # above (and get_league_waivers below), inlined here rather than shared
    # since neither of those two already factors it into a helper.
    injury_context: dict[str, Any] = {}
    settings = league_value_settings.detect_league_value_settings_from_payload(league)
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if not valued.empty:
        score_field = league_value_settings.valuation_score_field(lens)
        roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
        roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()
        if not roster_df.empty:
            lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)
            injury_context = trade_analyzer_fit.roster_injury_context(
                roster_df, lineup_df, taxi_player_ids=my_roster.get("taxi")
            )

    rankings_row: dict[str, Any] | None = None
    total_teams: int | None = None
    rankings_frame = league_rankings.build_league_rankings_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if not rankings_frame.empty:
        total_teams = int(len(rankings_frame))
        match = rankings_frame[rankings_frame["roster_id"].astype(str) == my_roster_id]
        if not match.empty:
            rankings_row = {
                key: _clean_json_value(value) for key, value in match.iloc[0].to_dict().items()
            }

    # Same already-cached rest-of-season Monte Carlo simulation the
    # standalone Playoff Odds screen (GET /v1/leagues/{id}/playoff-odds)
    # calls — "Where You Stand" asked Power Rank/Draft Capital Rank/record
    # but never this, even though it's the already-computed answer to
    # exactly the question GM Plan is trying to answer. Not-ready states
    # (offseason, no_playoff_format, no_rankings_data, unavailable) come
    # back as `reason` with an empty `teams` list — same honest-degradation
    # contract the dedicated endpoint uses, so there's simply no match
    # below and modules.gm_plan omits the fact rather than fabricating one.
    playoff_odds_result = playoff_simulator.build_league_playoff_odds_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    my_playoff_odds: dict[str, Any] | None = None
    for team in playoff_odds_result.get("teams") or []:
        if str(team.get("roster_id") or "") == my_roster_id:
            my_playoff_odds = team
            break

    trade_idea_records: list[dict[str, Any]] = []
    # Past the deadline: skip idea generation entirely — GM Plan shows the
    # "trades reopen after the season" state instead (modules.gm_plan).
    if not trade_window["trade_deadline_passed"]:
        try:
            team_strategy, _ = _fetch_gm_stance_with_set_flag(
                config, access_token, user_id=user_id, league_id=league_id
            )
            gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
                config, user_id, access_token, league_id
            )
            trade_idea_records = trade_hub_engine.generate_trade_idea_records_cached(
                league_id=league_id,
                roster_id=int(my_roster.get("roster_id")),
                strategy=team_strategy,
                lens=lens,
                players_db_path=PLAYERS_DB_PATH,
                untouchable_player_ids=gm_untouchable_ids,
                gm_target_player_ids=gm_target_ids,
                team_stance=declared_team_stance,
                keeper_round_penalty=_trade_idea_keeper_round_penalty(user, league_id),
            )
        except (TypeError, ValueError):
            trade_idea_records = []

    roster_settings = my_roster.get("settings") or {}
    record = {
        "wins": roster_settings.get("wins"),
        "losses": roster_settings.get("losses"),
        "ties": roster_settings.get("ties"),
    }

    plan = gm_plan.build_gm_plan(
        team_stance=declared_team_stance,
        season_phase=season_phase,
        rankings_row=rankings_row,
        total_teams=total_teams,
        record=record,
        playoff_odds=my_playoff_odds,
        trade_ideas=trade_idea_records,
        injury_context=injury_context,
        trade_deadline_passed=bool(trade_window["trade_deadline_passed"]),
    )

    return {
        "ok": True,
        "quiet": False,
        "reason": "",
        "is_premium": True,
        "upsell": None,
        **plan,
        "trade_window": trade_window,
    }


# Display order for My Team's starters section — matches
# modules.team_eval.suggest_optimal_lineup's own slot-assignment order.
# Bench keeps the frame's existing sort_score-descending order untouched.
_LINEUP_SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX", "WR/RB", "K", "DEF", "DL", "LB", "DB", "IDP_FLEX"]


def _matchup_player_identity_fields(row: pd.Series, score_field: str) -> dict[str, Any]:
    """Shared player identity/analytics fields for a matchup lineup row.

    injury_label, not raw injury_status, is what a client renders as the
    injury tag: unavailability lives in EITHER Sleeper field — a weekly
    "Questionable"/"Out" arrives on `injury_status`, while IR/PUP/
    season-ending arrives on `status` with `injury_status` often blank — so
    a pill driven by injury_status alone silently drops exactly the players
    who are most unavailable. modules.rankings.injury_display_label is the
    one place that resolution lives (the web dossier reads the same
    injury_level severity behind it).

    The single place both the suggested-lineup projection
    (`_project_lineup_row`) and the real-current-lineup projection
    (`_project_real_starter_row`) build name/position/team/tier/injury
    fields, so the two lineup views on the matchup screen can never drift
    into showing different identity data for the same player.
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
        "tier": _clean_json_value(row.get("player_tier")),
        "score": _clean_json_value(row.get(score_field)),
        "opportunity_label": _clean_json_value(row.get("opportunity_label")),
        # 0-99 "OVR" badge — see player_quick_view.overall_ratings_for_pool.
        # _suggested_lineup_split computes this over the FULL league pool
        # (every eligible player at the position), not just this roster's
        # dozen-odd players, and stashes it here before slicing to the roster.
        "overall_rating": _clean_json_value(row.get("_overall_rating_col")),
    }


def _project_lineup_row(
    row: pd.Series, score_field: str, *, reserve_ids: set[str], taxi_ids: set[str]
) -> dict[str, Any]:
    """One SUGGESTED (season-value) lineup row for the client.

    `roster_slot` is a completely separate concept from injury_label: it's
    WHERE the manager parked this player in Sleeper (starter/bench/taxi/
    ir), resolved via `_roster_slot_for_player` — the same function
    `_roster_relationship_map` uses — so a genuine IR/taxi placement and a
    merely-scratched healthy bench player never collapse into one
    indistinguishable "bench" bucket on the client.
    """

    player_id = str(row.get("player_id") or "")
    suggested_starter = bool(row.get("suggested_starter"))
    fields = _matchup_player_identity_fields(row, score_field)
    fields.update(
        {
            # The lineup builder's own availability call, so the client flags
            # a ruled-out starter (only ever slotted when nothing healthy
            # could fill the slot) instead of presenting him as a clean start.
            "ruled_out": bool(row.get("ruled_out")),
            "slot": _clean_json_value(row.get("slot")),
            "suggested_starter": suggested_starter,
            "roster_slot": _roster_slot_for_player(
                player_id, reserve_ids=reserve_ids, taxi_ids=taxi_ids, is_starter=suggested_starter
            ),
            # Weekly lineup gate (additive): "Bye" / "Out" / "IR" / "PUP" /
            # "Suspended" when this player can't start this week, else null.
            # Null everywhere when there's no current week (offseason).
            "start_ineligible_reason": _clean_json_value(row.get("start_ineligible_reason")),
            "on_bye": bool(row.get("on_bye") or False),
            # True when this player's own NFL game has kicked off, so Sleeper
            # has locked him (a started player on the bench cannot be started).
            "game_locked": bool(row.get("game_locked") or False),
            # The points figure this week's lineup was ranked on, and where
            # it came from: "projection" (this week's real projection),
            # "value_estimate" (no projection — matched to the projected
            # player nearest in season value), "value" (no projections at
            # all, season-value order), or null.
            "lineup_points": _clean_json_value(row.get("lineup_points")),
            "lineup_points_basis": _clean_json_value(row.get("lineup_points_basis")),
        }
    )
    return fields


def _reinstated_inactive_roster_rows(
    missing_player_ids: set[str],
    *,
    players_lookup: dict[str, Any] | None,
    valued: pd.DataFrame | None = None,
    settings: dict[str, Any] | None = None,
    score_field: str = "dynasty_score",
    valued_cache_key: str | None = None,
) -> list[dict[str, Any]]:
    """Real, fully-valued rows for genuinely-rostered players the valued pool
    dropped — not just identity placeholders.

    modules.player_eligibility.filter_current_fantasy_players treats a
    literal Sleeper `status` of "Inactive" as no-longer-a-current-player —
    correct for every OTHER recommendation surface (rankings, waivers,
    trade search: you don't want those recommending a ghost). But a real
    Sleeper roster can still literally list that player (the injury-
    awareness audit's exact finding: a season-ending/placeholder "Inactive"
    status silently vanished a rostered player from both the suggested
    starters AND bench here, with no explanation). Reinstated ONLY here,
    scoped to this one roster's own lineup view — never silently hidden,
    never fabricated healthy.

    Deliberately narrow: only literal "Inactive" is reinstated.
    Retired/historical/deceased players really are gone even on a stale
    Sleeper roster, so those correctly stay excluded.

    A real score/tier/opportunity_label IS computed here now (previously
    left blank — coridian_, 2026-10-16: "IR players don't have values for
    some reason... fix it properly no bandaid fix"), via the exact same
    production valuation code every other player goes through:
    modules.rankings.hydrate_reconciled_valuations_from_cache (the same
    mechanism structured_player_refresh.py already uses for newly-
    reconciled identities, reading disk-cached market/stats data, never a
    live network call) runs the real market/age/production/scarcity/role
    pipeline for just these reinstated rows against `valued` as the
    reference population, then modules.league_value_settings.
    apply_valuation_lens re-runs on `valued` + the reinstated rows
    TOGETHER (never the reinstated rows alone — tier assignment is
    percentile-relative to the real population, so computing it over 1-2
    rows in isolation would be meaningless) so dynasty_score/value_score/
    rebuild_score/player_tier/opportunity_label all come out exactly as
    they would have if this player had never been dropped from the pool in
    the first place. `valued`/`settings` are optional (both call sites
    always have them in practice) purely so a caller that genuinely can't
    supply them still gets identity-only rows rather than an error —
    modules.team_eval.suggest_optimal_lineup's own injury_level/
    is_ruled_out logic (which already treats a literal "Inactive" status as
    ruled out, see modules.rankings.injury_level) still naturally keeps a
    reinstated row out of a starting slot unless nothing else is available
    at the position, same as any other ruled-out player — a real score here
    doesn't change that.
    """

    identity_rows: list[dict[str, Any]] = []
    for player_id in missing_player_ids:
        raw = (players_lookup or {}).get(player_id)
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "").strip()
        if status.casefold() != "inactive":
            continue
        record = rankings.normalize_player_record(player_id, raw)
        if not record.get("name"):
            record["name"] = f"Player {player_id}"
        identity_rows.append(record)

    if not identity_rows:
        return []

    if valued is None or valued.empty or not settings:
        # No reference population to value against — identity only, same
        # as this function's original behavior.
        return [
            {
                "player_id": rec["player_id"],
                "name": rec["name"],
                "position": rec["position"],
                "team": rec["team"],
                "age": rec["age"],
                "status": rec["status"],
                "injury_status": rec["injury_status"],
                "player_tier": None,
                "opportunity_label": None,
            }
            for rec in identity_rows
        ]

    # Performance audit, 2026-10-21: scoring these rows re-runs the
    # valuation pipeline (disk-cached stats/market reads plus
    # apply_valuation_lens over the WHOLE pool) on every My Team and Matchup
    # request, up to four times per Matchup (both sides' suggested and real
    # lineups), warm caches or not -- most of those endpoints' CPU whenever a
    # roster holds an Inactive player. The result is a pure function of the
    # valued pool, these identity rows, the league settings, the score field
    # and the disk caches hydrate reads, so it is shared under exactly that
    # key: the valued pool's own cache version (which already embeds its
    # 120s bucket) plus each disk cache's mtime/size. Same TTL as the pool.
    # It can never be fresher or staler than the pool it was computed
    # against. A frame that didn't come straight from
    # build_valued_players_frame_cached has no version and is scored
    # uncached, exactly as before.
    if valued_cache_key is None:
        valued_cache_key = league_value_settings.valued_players_frame_cache_key(valued)
    if not valued_cache_key:
        return _score_reinstated_inactive_rows(identity_rows, valued, settings, score_field)
    cache_key = redis_cache.build_cache_key(
        "reinstated_inactive_rows",
        valued_cache_key,
        score_field,
        json.dumps(settings, sort_keys=True, default=str),
        json.dumps(identity_rows, sort_keys=True, default=str),
        rankings.reconciled_valuation_cache_versions(),
    )
    try:
        rows = redis_cache.redis_single_flight_cache(
            cache_key=cache_key,
            ttl_seconds=league_value_settings.VALUED_PLAYERS_FRAME_TTL_SECONDS,
            compute=lambda: _score_reinstated_inactive_rows(identity_rows, valued, settings, score_field),
        )
    except Exception:
        rows = _score_reinstated_inactive_rows(identity_rows, valued, settings, score_field)
    return [dict(row) for row in rows]


def _score_reinstated_inactive_rows(
    identity_rows: list[dict[str, Any]],
    valued: pd.DataFrame,
    settings: dict[str, Any],
    score_field: str,
) -> list[dict[str, Any]]:
    """The scoring half of _reinstated_inactive_roster_rows (see its
    docstring): real valuation for already-identified Inactive rows,
    against `valued` as the reference population."""

    candidates = pd.DataFrame.from_records(identity_rows)
    hydrated = rankings.hydrate_reconciled_valuations_from_cache(valued, candidates)
    # valuation_lens only affects a Redraft-specific blend ratio and which
    # score field assign_player_tiers treats as primary — dynasty_score/
    # value_score/rebuild_score are all computed every call regardless, so
    # any of the 3 real lens names is safe here; this just avoids needing a
    # 4th parameter threaded through both call sites for a value that
    # barely matters.
    lens = next(
        (
            name
            for name, field in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD.items()
            if field == score_field
        ),
        "Dynasty",
    )
    combined = pd.concat([valued, hydrated], ignore_index=True, sort=False)
    combined = league_value_settings.apply_valuation_lens(combined, lens, settings)
    # coridian_, 2026-10-19: "some IR players are still not listed with an
    # overall [rating]" — real repro: this function already computes a real
    # score/tier for a reinstated row (see this function's own docstring for
    # that earlier fix), but the 0-99 "overall rating" badge is a SEPARATE
    # percentile column (_overall_rating_col) that _suggested_lineup_split
    # computes once over `valued` BEFORE these rows exist, so a reinstated
    # row got concatenated in with no value for it at all (silently NaN,
    # not zero) — the row had a real Value but no OVR gauge. Computed here,
    # over the same `combined` population scored/tiered above, for the
    # same percentile-needs-a-real-population reason already documented.
    combined["_overall_rating_col"] = player_quick_view.overall_ratings_for_pool(
        combined, score_column=score_field
    )
    reinstated_ids = {rec["player_id"] for rec in identity_rows}
    scored = combined[combined["player_id"].astype(str).isin(reinstated_ids)]

    rows: list[dict[str, Any]] = []
    for _, row in scored.iterrows():
        rows.append(
            {
                "player_id": str(row.get("player_id") or ""),
                "name": _clean_json_value(row.get("name")),
                "position": _clean_json_value(row.get("position")),
                "team": _clean_json_value(row.get("team")),
                "age": _clean_json_value(row.get("age")),
                "status": _clean_json_value(row.get("status")),
                "injury_status": _clean_json_value(row.get("injury_status")),
                "player_tier": _clean_json_value(row.get("player_tier")),
                "opportunity_label": _clean_json_value(row.get("opportunity_label")),
                "_overall_rating_col": _clean_json_value(row.get("_overall_rating_col")),
                score_field: _clean_json_value(row.get(score_field)),
            }
        )
    return rows


def _idp_lineup_frame_rows(
    idp_result: dict[str, Any],
    roster_player_ids: set[str],
    players_lookup: dict[str, Any] | None,
    score_field: str,
) -> list[dict[str, Any]]:
    """A roster's defenders as lineup-frame rows. ``score_field`` carries the
    IDP model value (None when below replacement: shown as no value, ranked
    last, never invented)."""

    from modules import idp_roster_rows

    rows: list[dict[str, Any]] = []
    for row in idp_roster_rows.roster_idp_rows(idp_result, roster_player_ids, players_lookup):
        rows.append(
            {
                "player_id": row["player_id"],
                "name": row["name"],
                "position": row["position"],
                "team": row["team"],
                "age": row["age"],
                "status": "Active",
                "injury_status": row["injury_status"],
                "player_tier": None,
                "opportunity_label": None,
                "_overall_rating_col": None,
                score_field: row["score"],
            }
        )
    return rows


def _team_defense_frame_rows(roster_player_ids: set[str], score_field: str) -> list[dict[str, Any]]:
    """Rostered team defenses (Sleeper player_id = NFL team abbreviation) as
    lineup-frame rows. The valued pool has no DEF rows, so identity comes from
    modules.team_defense; every valuation field stays null (no invented
    score, tier, rating or projection)."""

    rows: list[dict[str, Any]] = []
    for player_id in sorted(roster_player_ids):
        identity = team_defense.team_defense_identity(player_id)
        if not identity:
            continue
        rows.append(
            {
                "player_id": player_id,
                "name": identity["name"],
                "position": identity["position"],
                "team": identity["team"],
                "age": None,
                "status": "Active",
                "injury_status": None,
                "player_tier": None,
                "opportunity_label": None,
                "_overall_rating_col": None,
                score_field: None,
            }
        )
    return rows


def _suggested_lineup_split(
    valued: pd.DataFrame,
    roster: dict[str, Any],
    settings: dict[str, Any],
    score_field: str,
    *,
    players_lookup: dict[str, Any] | None = None,
    projection_context: "_ProjectionContext | None" = None,
    meta: dict[str, Any] | None = None,
    idp_result: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One roster's suggested starters (slot-ordered) and bench.

    In an IDP league (``settings["idp_slots"]``) the roster's defenders join
    the frame at their IDP-model value (``idp_result``) so DL/LB/DB/IDP_FLEX
    slots are filled; non-IDP leagues are untouched.

    With a `projection_context` (a current NFL week exists) this is THIS
    WEEK's lineup: players on bye or ruled out never start (their slot
    stays open, listed in `meta["open_slots"]`), and starters rank by this
    week's projected points, falling back to season value only where no
    projection exists (see suggest_optimal_lineup's weekly mode). Every row
    then also carries its `projection`. Without one (offseason, or the
    projection inputs failed to load) it's the season-value lineup.

    The single place /my-team and /matchup both run
    modules.team_eval.suggest_optimal_lineup and project its rows, so the
    two surfaces can never drift into showing different "best lineup"
    answers for the same roster. Each row also carries its real Sleeper
    `roster_slot` (ir/taxi/starter/bench — see `_roster_slot_for_player`),
    so a genuine IR/taxi placement reads distinctly from an ordinary
    scratched bench player on both /my-team and /matchup.
    """

    roster_player_ids = {str(pid) for pid in (roster.get("players") or []) if pid}
    reserve_ids, taxi_ids = _roster_reserve_taxi_ids(roster)
    # Read before the copy below: only the exact frame the valued cache
    # handed out carries its cache version (see
    # _reinstated_inactive_roster_rows). The copy only adds the derived
    # _overall_rating_col, which the reinstated scoring recomputes itself.
    valued_cache_key = league_value_settings.valued_players_frame_cache_key(valued)

    # Overall rating is percentiled against the full league-eligible pool
    # (every rosterable player at the position), not the dozen players on
    # this one roster — a roster's own per-position pool is almost always
    # thinner than PERCENTILE_MIN_POOL and would rate every starter a 99.
    # Attached to `valued` before the roster slice below so it survives
    # suggest_optimal_lineup's copy (which preserves incoming columns).
    if "_overall_rating_col" not in valued.columns:
        valued = valued.copy()
        valued["_overall_rating_col"] = player_quick_view.overall_ratings_for_pool(
            valued, score_column=score_field
        )

    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()

    present_ids = set(roster_df["player_id"].astype(str)) if not roster_df.empty else set()
    missing_ids = roster_player_ids - present_ids
    if missing_ids and players_lookup:
        reinstated_rows = _reinstated_inactive_roster_rows(
            missing_ids,
            players_lookup=players_lookup,
            valued=valued,
            settings=settings,
            score_field=score_field,
            valued_cache_key=valued_cache_key,
        )
        if reinstated_rows:
            roster_df = pd.concat([roster_df, pd.DataFrame(reinstated_rows)], ignore_index=True, sort=False)

    # Rostered team defenses are not in the valued pool: add them with real
    # identity only (see _team_defense_frame_rows).
    have_ids = set(roster_df["player_id"].astype(str)) if not roster_df.empty else set()
    team_defenses = _team_defense_frame_rows(roster_player_ids - have_ids, score_field)
    if team_defenses:
        roster_df = pd.concat([roster_df, pd.DataFrame(team_defenses)], ignore_index=True, sort=False)

    if settings.get("idp_slots") and idp_result and idp_result.get("idp"):
        defenders = _idp_lineup_frame_rows(idp_result, roster_player_ids, players_lookup, score_field)
        have = set(roster_df["player_id"].astype(str)) if not roster_df.empty else set()
        defenders = [d for d in defenders if d["player_id"] not in have]
        if defenders:
            roster_df = pd.concat([roster_df, pd.DataFrame(defenders)], ignore_index=True, sort=False)

    projections_by_id: dict[str, dict[str, Any]] = {}
    if projection_context is not None:
        projections_by_id, weekly_points, bye_ids = _weekly_lineup_inputs(roster_df, projection_context)
        current_starters = {str(pid) for pid in (roster.get("starters") or []) if pid and str(pid) != "0"}
        # Without a real lineup on record we cannot tell who is locked in vs
        # locked out, so the kickoff lock only applies to a roster that has one.
        started_ids = _started_game_player_ids(roster_df, projection_context) if current_starters else set()
        lineup_df = suggest_optimal_lineup(
            roster_df,
            settings,
            score_field=score_field,
            weekly_points=weekly_points,
            bye_player_ids=bye_ids,
            started_player_ids=started_ids,
            locked_starter_ids=started_ids & current_starters,
        )
    else:
        lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)

    players = [
        _project_lineup_row(row, score_field, reserve_ids=reserve_ids, taxi_ids=taxi_ids)
        for _, row in lineup_df.iterrows()
    ]
    if projection_context is not None:
        for player in players:
            player["projection"] = projections_by_id.get(str(player.get("player_id") or ""))
    starters = [p for p in players if p["suggested_starter"]]
    starters.sort(
        key=lambda p: _LINEUP_SLOT_ORDER.index(p["slot"]) if p["slot"] in _LINEUP_SLOT_ORDER else len(_LINEUP_SLOT_ORDER)
    )
    bench = [p for p in players if not p["suggested_starter"]]
    if meta is not None:
        meta["open_slots"] = lineup_open_slots(lineup_df, settings)
        basis = SEASON_VALUE_BASIS
        if projection_context is not None:
            basis = (
                WEEKLY_PROJECTION_BASIS
                if any(p.get("lineup_points_basis") in ("projection", "value_estimate") for p in players)
                else WEEKLY_AVAILABILITY_BASIS
            )
        meta["lineup_basis"] = basis
        meta["week"] = projection_context.week if projection_context is not None else None
    return starters, bench


def _weekly_lineup_inputs(
    roster_df: pd.DataFrame, projection_context: "_ProjectionContext"
) -> tuple[dict[str, dict[str, Any]], dict[str, float], set[str]]:
    """This week's projection summary, rankable points and bye flag for
    every player on one roster, from the request's shared
    `_ProjectionContext` (nothing refetched per player).

    A player is on bye when his projection says so (`bye_week`) or his
    team's real schedule (modules.nfl_schedule) shows a bye that week —
    the schedule check covers players the projection can't resolve.
    """

    projections: dict[str, dict[str, Any]] = {}
    weekly_points: dict[str, float] = {}
    bye_ids: set[str] = set()
    if roster_df.empty or "player_id" not in roster_df.columns:
        return projections, weekly_points, bye_ids

    bye_by_team: dict[str, bool] = {}

    def team_on_bye(team: str) -> bool:
        if not team or projection_context.games is None:
            return False
        if team not in bye_by_team:
            try:
                matchup = nfl_schedule.team_matchup_for_week(
                    team, projection_context.week, projection_context.season, games=projection_context.games
                )
            except Exception:
                matchup = None
            bye_by_team[team] = bool(matchup and matchup.get("bye"))
        return bye_by_team[team]

    teams = roster_df["team"].tolist() if "team" in roster_df.columns else [None] * len(roster_df)
    for player_id, team in zip(roster_df["player_id"].astype(str).tolist(), teams):
        if not player_id or player_id in projections:
            continue
        try:
            projection = _weekly_projection_for_player(
                player_id,
                projection_context.week,
                projection_context.season,
                players_lookup=projection_context.players_lookup,
                weekly_stats=projection_context.weekly_stats,
                defense_strength=projection_context.defense_strength,
                team_qb_pass_attempts_by_team=projection_context.team_qb_pass_attempts_by_team,
            )
        except Exception:
            projection = None
        projections[player_id] = projection
        status = str((projection or {}).get("status") or "")
        team_code = str(team or "").strip().upper() if isinstance(team, str) else ""
        if status == "bye_week":
            bye_ids.add(player_id)
        elif status == "ok":
            if isinstance((projection or {}).get("point_estimate"), (int, float)):
                weekly_points[player_id] = float(projection["point_estimate"])
        elif status in _PROJECTION_STATUSES_WITH_RESOLVED_GAME:
            # The projection already found this player's real game this
            # week (just no usable trend), so he isn't on bye.
            continue
        elif team_on_bye(team_code):
            # The projection couldn't resolve his team/schedule (unknown
            # player, unsupported position like K/DEF, no schedule row):
            # fall back to the roster frame's team.
            bye_ids.add(player_id)
    return projections, weekly_points, bye_ids


def _started_game_player_ids(roster_df: pd.DataFrame, projection_context: "_ProjectionContext") -> set[str]:
    """Players on this roster whose own NFL game has kicked off this week
    (Sleeper locks them in or out of the lineup from that moment). Unknown
    kickoff data means "not started": the lock never invents itself."""

    started: set[str] = set()
    if roster_df.empty or "player_id" not in roster_df.columns or projection_context.games is None:
        return started
    teams = roster_df["team"].tolist() if "team" in roster_df.columns else [None] * len(roster_df)
    started_by_team: dict[str, bool] = {}
    for player_id, team in zip(roster_df["player_id"].astype(str).tolist(), teams):
        team_code = str(team or "").strip().upper() if isinstance(team, str) else ""
        if not player_id or not team_code:
            continue
        if team_code not in started_by_team:
            started_by_team[team_code] = bool(
                _player_game_state(team_code, projection_context).get("game_started")
            )
        if started_by_team[team_code]:
            started.add(player_id)
    return started


_PROJECTION_STATUSES_WITH_RESOLVED_GAME = frozenset({"insufficient_player_data", "no_opponent"})


def _league_idp_result(league_id: str, league: dict[str, Any]) -> dict[str, Any]:
    """Cached IDP model output for a league; empty on any failure so My Team
    and Waivers never break over a defender-stats hiccup."""

    if not idp_scoring.league_has_idp(league.get("roster_positions")):
        return {"idp": False, "players": []}
    try:
        from modules import idp_league_values

        return idp_league_values.cached_league_idp_values(league_id, league)
    except Exception:
        return {"idp": False, "players": []}


def _my_team_idp_rows(
    league_id: str, league: dict[str, Any], roster_player_ids: Any, players_lookup: dict[str, Any] | None
) -> list[dict[str, Any]]:
    from modules import idp_roster_rows

    return idp_roster_rows.roster_idp_rows(_league_idp_result(league_id, league), roster_player_ids, players_lookup)


def _waivers_idp_rows(league_id: str, league: dict[str, Any], rosters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from modules import idp_roster_rows

    rostered = {str(pid) for r in rosters for pid in (r.get("players") or []) if pid is not None}
    return idp_roster_rows.free_agent_idp_rows(_league_idp_result(league_id, league), rostered)


@app.get("/v1/leagues/{league_id}/my-team")
@_with_sleeper_as_of
def get_league_my_team(
    league_id: str = Depends(resolve_league_path_id),
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

    # Same (league_id, lens)-scoped cache /rankings and friends share — see
    # league_value_settings.build_valued_players_frame_cached's docstring.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if valued.empty:
        return {"ok": True, "starters": [], "bench": [], "reason": "no_player_data"}

    score_field = league_value_settings.valuation_score_field(lens)

    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    if not roster_player_ids:
        return {"ok": True, "starters": [], "bench": [], "reason": "empty_roster"}

    # Best-effort — a hiccup fetching Sleeper's raw player directory must
    # never break this endpoint; it only means a rostered-but-Inactive
    # player can't be reinstated into the lineup this one request.
    try:
        my_team_players_lookup = sleeper.get_players()
    except Exception:
        my_team_players_lookup = {}
    # This week's lineup while the league is in season: byes and ruled-out
    # players never start, weekly projections rank the rest (see
    # _suggested_lineup_split). Offseason / no week: season-value lineup.
    lineup_meta: dict[str, Any] = {}
    idp_result = _league_idp_result(league_id, league) if settings.get("idp_slots") else None
    starters, bench = _suggested_lineup_split(
        valued,
        my_roster,
        settings,
        score_field,
        players_lookup=my_team_players_lookup,
        projection_context=_build_projection_context(_league_current_lineup_week(league)),
        meta=lineup_meta,
        idp_result=idp_result,
    )
    lineup_basis = lineup_meta.get("lineup_basis", SEASON_VALUE_BASIS)

    best_ball = league_calendar.is_best_ball(league)
    return {
        "ok": True,
        "starters": starters,
        "bench": bench,
        # Additive: rostered defenders, IDP leagues only ([] otherwise).
        # Defenders already placed in the lineup (starters/bench) are not repeated.
        "idp_players": _my_team_idp_rows(
            league_id,
            league,
            roster_player_ids
            - {str(p.get("player_id")) for p in starters}
            - {str(p.get("player_id")) for p in bench},
            my_team_players_lookup,
        ),
        "reason": "",
        "roster_id": str(my_roster.get("roster_id") or ""),
        # Additive (older clients ignore these).
        "week": lineup_meta.get("week"),
        "lineup_basis": lineup_basis,
        "lineup_basis_label": _LINEUP_BASIS_LABELS.get(lineup_basis, SEASON_VALUE_BASIS_LABEL),
        "open_slots": lineup_meta.get("open_slots", []),
        # Additive league-calendar context (modules.league_calendar): in a
        # best ball league Sleeper picks the lineup itself, so clients hide
        # the suggested-lineup/start-sit framing; Trade Finder reads
        # trade_window to show the deadline-passed state up front.
        "best_ball": best_ball,
        "lineup_advice_message": league_calendar.BEST_BALL_LINEUP_MESSAGE if best_ball else "",
        "trade_window": league_calendar.trade_window(league),
    }


@app.get("/v1/leagues/{league_id}/keepers")
def get_league_keepers(
    league_id: str = Depends(resolve_league_path_id),
    lens: str = "Dynasty",
    round_penalty: int | None = None,
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Keeper tags, estimated surplus and keep-or-cut candidates (keeper leagues).

    Uses only real Sleeper data (see modules.keepers); cost rounds are
    estimates because Sleeper exposes no machine-readable keeper cost rule.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(status_code=422, detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD))
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}
    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return {"ok": True, "is_keeper_league": False, "reason": reason}
    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)
    if not settings.get("_keeper_mode"):
        return {"ok": True, "is_keeper_league": False, "reason": "not_keeper_league"}
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    league_settings = league.get("settings") or {}
    current_picks, previous_picks = _keeper_draft_picks(league_id, league)
    if round_penalty is None:
        round_penalty = _stored_keeper_round_penalty(config, user_id, str(user.get("_access_token") or ""), league_id)
    report = keepers_module.build_keeper_report(
        roster=my_roster,
        valued=valued,
        score_field=league_value_settings.valuation_score_field(lens),
        num_teams=int(league.get("total_rosters") or league_settings.get("num_teams") or 12),
        max_keepers=league_settings.get("max_keepers"),
        current_picks=current_picks,
        previous_picks=previous_picks,
        round_penalty=round_penalty,
    )
    return {
        "ok": True,
        "is_keeper_league": True,
        "reason": "",
        "estimate_note": (
            "Sleeper has no machine-readable keeper cost rule. Cost round is the player's last draft round "
            "(or the round a keeper pick was assigned), shifted by your round penalty; surplus is estimated "
            "against the typical player taken at that round."
        ),
        **report,
    }


def _keeper_draft_picks(league_id: str, league: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """(this season's draft picks, previous season's draft picks) from Sleeper."""

    current_picks = keepers_module.latest_draft_picks(
        sleeper.get_league_drafts(league_id), sleeper.get_draft_picks
    )
    previous_id = str(league.get("previous_league_id") or "")
    previous_picks = (
        keepers_module.latest_draft_picks(sleeper.get_league_drafts(previous_id), sleeper.get_draft_picks)
        if previous_id and previous_id != "0"
        else []
    )
    return current_picks, previous_picks


def _stored_keeper_round_penalty(config: dict, user_id: str, access_token: str, league_id: str) -> int:
    """User-set keeper round penalty for a league (user_settings blob); 0 when unset or on any failure."""

    if not user_id:
        return 0
    try:
        current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
        if error:
            return 0
        stored = (current.get("settings") or {}).get("keeper_round_penalty_by_league") or {}
        return keepers_module.clamp_round_penalty(stored.get(league_id))
    except Exception:
        return 0


def _trade_idea_keeper_round_penalty(user: dict[str, Any], league_id: str) -> int:
    """The user's stored keeper round penalty for trade-idea pricing; 0 for
    non-keeper leagues or on any failure (no extra storage read in that case)."""

    try:
        league = sleeper.get_league(league_id)
        if not league or not league_value_settings.detect_league_value_settings_from_payload(league).get("_keeper_mode"):
            return 0
        return _stored_keeper_round_penalty(
            auth_supabase.get_supabase_config(),
            str(user.get("id") or ""),
            str(user.get("_access_token") or ""),
            league_id,
        )
    except Exception:
        return 0


class KeeperSettingsRequest(BaseModel):
    round_penalty: int = Field(ge=0, le=keepers_module.MAX_ROUND_PENALTY)


@app.post("/v1/leagues/{league_id}/keeper-settings")
def set_league_keeper_settings(
    body: KeeperSettingsRequest,
    league_id: str = Depends(resolve_league_path_id),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Store the user's keeper round penalty for this league (read-modify-write
    on the user_settings blob, like /v1/preferences)."""

    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, "round_penalty": 0}
    settings = dict(current.get("settings") or {})
    by_league = dict(settings.get("keeper_round_penalty_by_league") or {})
    by_league[league_id] = body.round_penalty
    settings["keeper_round_penalty_by_league"] = by_league
    payload = account_store.build_user_settings_payload(user_id=user_id, settings=settings)
    ok, _ = account_store.upsert_user_settings(config, access_token, payload)
    return {"ok": bool(ok), "round_penalty": body.round_penalty}


def _stored_league_type_override(config: dict, user_id: str, access_token: str, league_id: str) -> str | None:
    """User-set league type override (user_settings blob); None when unset or on any failure."""

    if not user_id:
        return None
    try:
        current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
        if error:
            return None
        stored = (current.get("settings") or {}).get("league_type_override_by_league") or {}
        return guillotine_module.clean_override(stored.get(league_id))
    except Exception:
        return None


@app.get("/v1/leagues/{league_id}/guillotine")
def get_league_guillotine(
    league_id: str = Depends(resolve_league_path_id),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Survival status and this week's chop line for guillotine/chopped leagues.

    Real Sleeper data only (see modules.guillotine). `chop_line` is null
    unless every alive roster has a real projection.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(status_code=422, detail="Unknown lens.")
    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    token = str(user.get("_access_token") or "")
    profile = _fetch_profile_fields(config, user_id, token) if user_id else {}
    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    not_gl = {"ok": True, "is_guillotine": False, "reason": reason}
    if my_roster is None:
        return not_gl
    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    rosters = sleeper.get_rosters(league_id) or []
    override = _stored_league_type_override(config, user_id, token, league_id)
    league_settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    try:
        week = int(league_settings.get("leg") or 0)
    except (TypeError, ValueError):
        week = 0
    in_season = str(league.get("status") or "") == "in_season" and week > 0
    past_weeks = {w: sleeper.get_matchups(league_id, w) or [] for w in range(1, week)} if in_season else {}
    detected = guillotine_module.detect(league, rosters, override, past_weeks)
    if not detected["is_guillotine"]:
        return {**not_gl, "reason": "not_guillotine", "league_type_override": override}
    status = guillotine_module.survival_status(my_roster, rosters, past_weeks)

    chop = None
    if in_season and status["alive"]:
        matchups = sleeper.get_matchups(league_id, week) or []
        entries = {str(m.get("roster_id")): m for m in matchups}
        alive_ids = [str(r.get("roster_id")) for r in rosters if r.get("players")]
        valued = league_value_settings.build_valued_players_frame_cached(
            league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
        )
        projection_context = _build_projection_context(week)
        if not valued.empty and projection_context is not None and all(rid in entries for rid in alive_ids):
            settings = league_value_settings.detect_league_value_settings_from_payload(league)
            score_field = league_value_settings.valuation_score_field(lens)
            positions = league.get("roster_positions") if isinstance(league.get("roster_positions"), list) else []
            projected: dict[str, float | None] = {}
            for rid in alive_ids:
                lineup = _real_current_lineup(
                    entries[rid], valued, score_field,
                    projection_context=projection_context, settings=settings, roster_positions=positions,
                )
                points = [matchup_win_probability.starter_expected_points(s) for s in lineup.get("real_starters") or []]
                complete = bool(points) and not lineup.get("real_empty_slots") and all(p is not None for p in points)
                projected[rid] = sum(points) if complete else None
            chop = guillotine_module.chop_line(alive_ids, projected, str(my_roster.get("roster_id")))
    return {
        "ok": True,
        "is_guillotine": True,
        "reason": "",
        "source": detected["source"],
        "league_type_override": override,
        "week": week if in_season else None,
        **status,
        "chop_line": chop,
    }


class LeagueTypeRequest(BaseModel):
    league_type: str


@app.post("/v1/leagues/{league_id}/league-type")
def set_league_type(
    body: LeagueTypeRequest,
    league_id: str = Depends(resolve_league_path_id),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Store a manual guillotine/standard override for this league ("auto" clears it)."""

    value = guillotine_module.clean_override(body.league_type)
    if value is None and body.league_type != "auto":
        raise HTTPException(status_code=422, detail="league_type must be guillotine, standard or auto")
    config = auth_supabase.get_supabase_config()
    access_token = str(user.get("_access_token") or "")
    user_id = str(user.get("id") or "")
    current, error = account_store.fetch_user_settings(config, access_token, user_id=user_id)
    if error:
        return {"ok": False, "league_type": None}
    settings = dict(current.get("settings") or {})
    by_league = dict(settings.get("league_type_override_by_league") or {})
    if value is None:
        by_league.pop(league_id, None)
    else:
        by_league[league_id] = value
    settings["league_type_override_by_league"] = by_league
    payload = account_store.build_user_settings_payload(user_id=user_id, settings=settings)
    ok, _ = account_store.upsert_user_settings(config, access_token, payload)
    return {"ok": bool(ok), "league_type": value}


def _empty_my_team_needs_response(settings: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "ok": True,
        "reason": reason,
        "show_franchise_construction": league_format_context.lead_with_franchise_construction(settings),
        "superflex": league_format_context.is_superflex(settings),
        "te_premium": league_format_context.is_te_premium(settings),
        "strengths": [],
        "weaknesses": [],
        "biggest_need": None,
        "position_groups": [],
    }


@app.get("/v1/leagues/{league_id}/my-team-needs")
def get_league_my_team_needs(
    league_id: str = Depends(resolve_league_path_id),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Roster-needs detail for My Team's Strength & Pressure / Position
    Groups / Biggest Need tiles — the pieces of the web app's My Team page
    (modules.my_team_ui.render_my_team_workspace) that GET .../my-team
    deliberately left out as "lineup view only" (see that endpoint's own
    docstring).

    Thin wrapper only: every field below comes from calling the exact same
    pure engines app.py's My Team route already calls for these sections —
    modules.team_eval.build_league_summary + get_team_vs_league for the
    league-relative position-strength list, modules.trade_analyzer_fit.
    build_team_needs_assessment (the same call GET .../waivers already
    makes for its own needed_positions) for per-position classification,
    and modules.roster_needs.select_need_headline for the Biggest Need
    headline — no new valuation or need-classification logic is introduced
    here, and the weaknesses filter below mirrors app.py's My Team route
    (short_term_need rooms that are not merely a temporary injury blip)
    byte-for-byte.
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
        return _empty_my_team_needs_response({}, reason=reason)

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if valued.empty:
        return _empty_my_team_needs_response(settings, reason="no_player_data")

    score_field = league_value_settings.valuation_score_field(lens)
    roster_player_ids = {str(pid) for pid in (my_roster.get("players") or [])}
    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()
    if roster_df.empty:
        return _empty_my_team_needs_response(settings, reason="empty_roster")

    lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)

    # League-relative room strength (QB/RB/WR/TE meaningfully above the
    # league's starter-weighted average) — same per-team summary frame
    # GET .../team-rankings' archetype column is refined from, read
    # directly here for the single list My Team's Strength & Pressure
    # "Strength" card needs. Best-effort: a Sleeper hiccup building the
    # league-wide summary degrades to an empty strengths list rather than
    # failing this endpoint's actual roster-needs data below.
    team_metrics: dict[str, Any] | None = None
    try:
        df_summary = build_league_summary(
            valued,
            league_id,
            score_field=score_field,
            current_score_field=score_field,
            lineup_settings=settings,
        )
        if not df_summary.empty:
            team_metrics = get_team_vs_league(df_summary, my_roster.get("roster_id"))
    except Exception:
        team_metrics = None
    strengths = [str(pos) for pos in ((team_metrics or {}).get("strengths") or [])]

    assessment = trade_analyzer_fit.build_team_needs_assessment(
        roster_df, team_metrics, settings, lineup_df=lineup_df, score_field=score_field
    )
    major_needed_positions = trade_analyzer_fit.get_needed_positions(
        roster_df, team_metrics, settings, include_fallback=False, assessment=assessment
    )
    weaknesses = [
        position
        for position in major_needed_positions
        if (
            assessment.for_position(position) is not None
            and assessment.for_position(position).classification == "short_term_need"
            and not assessment.for_position(position).temporary_injury_pressure
        )
    ]

    need_display = roster_needs.select_need_headline(assessment)
    biggest_need = {
        "label": str(need_display.get("label") or "").replace("Biggest Team Need", "Biggest Need"),
        "value": need_display.get("value"),
        "note": need_display.get("note"),
    }

    position_groups = [
        {
            "position": item.position,
            "classification": item.classification,
            "reasons": list(item.reasons),
            "upgrade_opportunity": bool(item.upgrade_opportunity),
            "temporary_injury_pressure": bool(item.temporary_injury_pressure),
        }
        for item in assessment.positions
    ]

    return {
        "ok": True,
        "reason": "",
        "show_franchise_construction": league_format_context.lead_with_franchise_construction(settings),
        "superflex": league_format_context.is_superflex(settings),
        "te_premium": league_format_context.is_te_premium(settings),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "biggest_need": biggest_need,
        "position_groups": position_groups,
    }


# The one sentence every matchup surface (API, mobile headline, tests)
# points at for what this comparison actually measures. ``modules.
# player_projections`` does now provide a real weekly points-projection
# data source (wired into the REAL current-week lineup below — see
# `_project_real_starter_row`/`_weekly_projection_for_player` — and into
# GET /v1/players/{id}/schedule), but this SUGGESTED lineup is deliberately
# left out of that: it is this app's best-roster recommendation in
# season-long value/opportunity terms (the same signal the rest of the app
# already computes), not a single week's matchup-dependent point estimate
# — mixing a short-term projection into "who should I roster as a starter"
# would make the recommendation swing on one week's matchup variance,
# which isn't what this view answers. Do not relabel this as "projected
# points" without deciding that tradeoff deliberately first.
SEASON_VALUE_BASIS = "season_value"
SEASON_VALUE_BASIS_LABEL = "Season-long value & opportunity signal — not a weekly points projection."

# Product owner approved (2026-10-21 logic audit): during the season the
# SUGGESTED lineup is a lineup for THIS week. Players on bye or ruled out
# (Out/IR/PUP/Suspended) never start, and starters rank by this week's
# projected points, using season value only where no projection exists.
# WEEKLY_AVAILABILITY_BASIS is the same weekly gate when no roster player
# has a usable projection (season-value order, byes/outs still excluded).
WEEKLY_PROJECTION_BASIS = "weekly_projection"
WEEKLY_PROJECTION_BASIS_LABEL = (
    "This week's lineup: ranked by projected points (season value where no projection exists); "
    "players on bye or ruled out don't start."
)
WEEKLY_AVAILABILITY_BASIS = "weekly_availability"
WEEKLY_AVAILABILITY_BASIS_LABEL = (
    "This week's lineup by season value; players on bye or ruled out don't start."
)
_LINEUP_BASIS_LABELS = {
    SEASON_VALUE_BASIS: SEASON_VALUE_BASIS_LABEL,
    WEEKLY_PROJECTION_BASIS: WEEKLY_PROJECTION_BASIS_LABEL,
    WEEKLY_AVAILABILITY_BASIS: WEEKLY_AVAILABILITY_BASIS_LABEL,
}

# The label for the OTHER matchup view: Sleeper's own real current-week
# lineup and live points (modules.sleeper.get_matchups' `starters` /
# `starters_points` / `points` fields), as opposed to SEASON_VALUE_BASIS
# above, which is this app's computed season-value lineup recommendation.
REAL_LINEUP_BASIS = "sleeper_actual_lineup"
REAL_LINEUP_BASIS_LABEL = "Your actual current-week lineup and live points, straight from Sleeper."

# Below this relative gap the two lineups are called even rather than
# implying a real edge — a season-value total is a coarse signal, and a
# sub-3% difference is well inside its noise.
_MATCHUP_EVEN_THRESHOLD = 0.03


def _matchup_starter_why(player: dict[str, Any], best_score_by_position: dict[str, float]) -> str:
    """Why this player is a suggested starter, in season-form terms only.

    Every clause comes from data that genuinely exists on the lineup row
    (tier, opportunity/workload label, season-value rank on this roster,
    injury tag). Deliberately says nothing about this week's opponent or
    expected points: a real weekly-projection/opponent-defense data source
    does now exist (``modules.player_projections``, surfaced on the REAL
    lineup's rows below), but this SUGGESTED lineup is scoped to season-
    long value terms only — see ``SEASON_VALUE_BASIS_LABEL``'s comment for
    why mixing the two here is deliberately out of scope rather than an
    oversight.
    """

    bits: list[str] = []
    # Weekly lineup (in season): lead with the number this start was
    # actually ranked on.
    projection = player.get("projection") if isinstance(player.get("projection"), dict) else {}
    points = projection.get("point_estimate")
    if player.get("lineup_points_basis") == "projection" and isinstance(points, (int, float)):
        opponent = str(projection.get("opponent") or "").strip()
        bits.append(f"Projected {points:.1f} pts" + (f" vs {opponent}" if opponent else ""))
    elif player.get("lineup_points_basis") == "value_estimate":
        bits.append("No projection yet — ranked on season value")
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
    *,
    players_lookup: dict[str, Any] | None = None,
    projection_context: "_ProjectionContext | None" = None,
    matchup_entry: dict[str, Any] | None = None,
    bench_out: list[dict[str, Any]] | None = None,
    idp_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One team's side of the matchup: identity, suggested starters, season-value total.

    `matchup_entry` (this roster's Sleeper matchup row), when given, lets
    each suggested starter carry the same live fields a real starter does:
    `actual_points` from Sleeper's `players_points` (every rostered player's
    real score this week, bench included) and `game_started`/`game_status`
    from his own NFL game. That keeps the Suggested and Actual lineup views
    on one scale while games are in progress.

    Both sides run the SAME modules.team_eval.suggest_optimal_lineup pass
    (via _suggested_lineup_split), so the comparison is apples-to-apples.
    That also means the opponent side is their best available lineup, not
    necessarily the lineup they've actually set in Sleeper — stated in the
    response as `starters_basis` so the client can say so out loud.

    `players_lookup` (modules.sleeper.get_players' raw directory) lets
    _suggested_lineup_split reinstate a genuinely rostered player whose
    literal "Inactive" status got him filtered out of `valued` upstream —
    see _reinstated_inactive_roster_rows.

    `projection_context`, when given, attaches each starter's this-week
    `projection` (point_estimate/low/high/confidence) via the same
    `_weekly_projection_for_player` the real lineup already uses — reusing
    data already fetched for `_real_current_lineup`, not a new source (see
    get_league_matchup's docstring note on why this view previously had no
    weekly projection at all: coridian_, 2026-10-17, "everyy player on the
    matchup screen needs a projection"). `None` when the caller couldn't
    build one (no live lineup to enrich yet) — each starter's `projection`
    is then `None` too, same honest-absence contract as everywhere else.
    """

    lineup_meta: dict[str, Any] = {}
    starters, _bench = _suggested_lineup_split(
        valued,
        roster,
        settings,
        score_field,
        players_lookup=players_lookup,
        projection_context=projection_context,
        meta=lineup_meta,
        idp_result=idp_result,
    )
    if bench_out is not None:
        # The lineup planner (get_league_matchup_what_if) needs the bench too,
        # with the same live fields a starter carries. Not part of the payload.
        for player in _bench:
            player.setdefault("projection", None)
            player.update(_player_game_state(player.get("team"), projection_context))
            player["actual_points"] = _players_points_for(matchup_entry, player.get("player_id"))
        bench_out.extend(_bench)

    best_score_by_position: dict[str, float] = {}
    for player in starters:
        position = str(player.get("position") or "").strip()
        score = player.get("score")
        if not position or not isinstance(score, (int, float)):
            continue
        best_score_by_position[position] = max(best_score_by_position.get(position, float("-inf")), float(score))

    for player in starters:
        player["why"] = _matchup_starter_why(player, best_score_by_position)
        # _suggested_lineup_split already attached this week's projection to
        # every row when a projection context exists (one computation per
        # player, reused here).
        player.setdefault("projection", None)
        player.update(_player_game_state(player.get("team"), projection_context))
        player["actual_points"] = _players_points_for(matchup_entry, player.get("player_id"))

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
        # Additive: what this side's suggested lineup was ranked on, and any
        # starting slots left open because nobody eligible could fill them
        # (bye / ruled out). See _suggested_lineup_split.
        "lineup_basis": lineup_meta.get("lineup_basis", SEASON_VALUE_BASIS),
        "lineup_basis_label": _LINEUP_BASIS_LABELS.get(
            lineup_meta.get("lineup_basis", SEASON_VALUE_BASIS), SEASON_VALUE_BASIS_LABEL
        ),
        "open_slots": lineup_meta.get("open_slots", []),
    }


def _players_points_for(matchup_entry: dict[str, Any] | None, player_id: Any) -> float | None:
    """This player's real points this week from Sleeper's `players_points`
    (keyed by player_id, bench included). None when Sleeper hasn't posted
    lineups yet or doesn't list him, never a fabricated 0."""

    if not matchup_entry or not matchup_entry.get("starters"):
        return None
    points_by_id = matchup_entry.get("players_points")
    if not isinstance(points_by_id, dict):
        return None
    value = points_by_id.get(str(player_id or ""))
    return round(float(value), 2) if isinstance(value, (int, float)) else None


def _player_game_state(team: Any, projection_context: "_ProjectionContext | None") -> dict[str, Any]:
    """This starter's own game state: `game_started`, `game_final` and
    `game_kickoff_at`, all from one modules.nfl_schedule row.

    `game_started`: whether THIS starter's own NFL game has actually kicked off this
    week — a different question from the roster-level `has_live_data` gate
    on `MatchupSide`, which only means Sleeper has locked the week's
    starters, not that any one player's game has begun. A real starter
    whose game hasn't started yet still reports `actual_points == 0` from
    Sleeper (nobody has played a snap), and a client needs this signal to
    know that a 0 isn't a real score yet — the product bug this exists to
    fix (coridian_: "the points... should not be zero... before any
    games").

    Sourced from modules.nfl_schedule's real kickoff time (nflverse's
    gameday/gametime, Eastern Time) for this player's team/week — the same
    real schedule data Player Detail's Schedule tab already reads, never a
    new invented concept. Returns None (unknown) when the signal isn't
    available (no team, bye week, schedule fetch hiccup, or an older
    season missing gameday/gametime) rather than guessing; callers fall
    back to "has this player actually scored a nonzero amount" in that
    case, which can only be true for a game that has started.

    `game_final` (nflverse has a final score on record) and
    `game_kickoff_at` (the real kickoff instant, ISO-8601 UTC) let the live
    win probability place an in-progress game on the clock (see
    modules.matchup_win_probability.game_fraction_remaining). Both are None
    when the schedule row isn't available, the same "unknown, never
    guessed" contract as `game_started`.
    """

    state: dict[str, Any] = {
        "game_started": None,
        "game_final": None,
        "game_kickoff_at": None,
        "game_status": None,
    }
    if projection_context is None or projection_context.games is None or not team:
        return state
    try:
        matchup = nfl_schedule.team_matchup_for_week(
            str(team), projection_context.week, projection_context.season, games=projection_context.games
        )
    except Exception:
        return state
    state["game_started"] = nfl_schedule.game_has_started(matchup)
    if matchup is not None:
        # Final implies kicked off (game_has_started is True once played).
        state["game_final"] = bool(matchup.get("played")) and state["game_started"] is True
        state["game_kickoff_at"] = matchup.get("kickoff_at") or None
        try:
            state["game_status"] = nfl_schedule.game_phase(matchup)
        except Exception:
            state["game_status"] = None
    return state


def _project_real_starter_row(
    row: pd.Series,
    score_field: str,
    actual_points: Any,
    *,
    projection_context: "_ProjectionContext | None",
    slot: str | None = None,
) -> dict[str, Any]:
    """One REAL current-week starter row: a player Sleeper says is actually
    starting this week, enriched via the same identity helper the suggested
    lineup uses, plus his real point total scored so far this week and (when
    `projection_context` is available) this week's per-game projection —
    additive, clearly separate from `actual_points`, never a substitute for
    it. See `_projection_summary_dict` for the honest-edge-case shape.
    """

    fields = _matchup_player_identity_fields(row, score_field)
    fields["actual_points"] = round(float(actual_points), 2) if isinstance(actual_points, (int, float)) else None
    fields["projection"] = (
        _weekly_projection_for_player(
            str(row.get("player_id") or ""),
            projection_context.week,
            projection_context.season,
            players_lookup=projection_context.players_lookup,
            weekly_stats=projection_context.weekly_stats,
            defense_strength=projection_context.defense_strength,
            team_qb_pass_attempts_by_team=projection_context.team_qb_pass_attempts_by_team,
        )
        if projection_context is not None
        else None
    )
    fields.update(_player_game_state(fields.get("team"), projection_context))
    fields["slot"] = slot
    return fields


@dataclasses.dataclass(frozen=True)
class _ProjectionContext:
    """Everything `_weekly_projection_for_player` needs, fetched/computed
    ONCE per matchup request rather than once per starter — see that
    function's own docstring for why a per-player refetch would be wasteful.

    `games` (modules.nfl_schedule's real games table) is additionally used
    by `_player_game_state` to tell whether a REAL starter's own game has
    actually kicked off yet — a separate question from the projection
    itself, but fetched here too so it's still only loaded once per
    request. None when the caller couldn't fetch it (best-effort, same
    fails-soft contract as every other field here); `_player_game_state`
    reports "unknown" rather than guessing in that case.
    """

    week: int
    season: int
    players_lookup: dict[str, Any]
    weekly_stats: dict[str, Any]
    defense_strength: dict[str, Any]
    games: pd.DataFrame | None = None
    team_qb_pass_attempts_by_team: dict[str, Any] | None = None


def _build_projection_context(week: int) -> "_ProjectionContext | None":
    """The shared per-request projection inputs for one NFL week, or None
    when there's no week or anything fails to load (fails soft: callers
    fall back to the season-value lineup with no per-player projection)."""

    if week <= 0:
        return None
    try:
        season = sleeper.default_player_stats_season()
        players_lookup = sleeper.get_players()
        weekly_stats = sleeper.get_season_player_stats(season=season, retain_weekly=True)
        return _ProjectionContext(
            week=week,
            season=season,
            players_lookup=players_lookup,
            weekly_stats=weekly_stats,
            defense_strength=player_projections.team_defense_points_allowed_by_position(
                season,
                upto_week=week - 1,
                weekly_stats=weekly_stats,
                players=players_lookup,
            ),
            games=nfl_schedule.load_games(),
            # Built ONCE per request: every projected player would otherwise
            # redo the same full players_lookup scan. See
            # team_qb_pass_attempts_by_week's own docstring.
            team_qb_pass_attempts_by_team=player_projections.team_qb_pass_attempts_by_week(
                players_lookup, weekly_stats
            ),
        )
    except Exception:
        return None


def _league_current_lineup_week(league: dict[str, Any]) -> int:
    """The NFL week a suggested lineup is for: the league's own
    `settings.leg` while the league is in season, else 0 (no weekly gate)."""

    if str(league.get("status") or "") != "in_season":
        return 0
    league_settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    try:
        return max(0, int((league_settings or {}).get("leg") or 0))
    except (TypeError, ValueError):
        return 0


def _real_current_lineup(
    matchup_entry: dict[str, Any],
    valued: pd.DataFrame,
    score_field: str,
    *,
    projection_context: "_ProjectionContext | None" = None,
    settings: dict[str, Any] | None = None,
    roster_positions: list[Any] | None = None,
    idp_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """This roster's ACTUAL current-week lineup and points, straight from Sleeper.

    `roster_positions` (the league's own Sleeper `roster_positions`) labels
    each real starter with the lineup `slot` he occupies — Sleeper's
    `starters` array is in the same order as the league's non-bench
    roster positions, and an unfilled slot is reported as "0". Unfilled
    slots are listed in `real_empty_slots` rather than dropped silently, so
    a partial lineup reads as partial.

    modules.sleeper.get_matchups already returns, per roster, `starters`
    (the player_ids this manager genuinely has starting this week in
    Sleeper — which may differ from `_suggested_lineup_split`'s season-value
    recommendation above), `starters_points` (a parallel array — same index
    order as `starters` — of each one's real point total scored so far this
    week, live during in-progress games and final once the week completes),
    and `points` (the roster's real total). Previously fetched and entirely
    discarded; surfaced here as-is, additive to the suggested-lineup view.

    `has_live_data` is False whenever Sleeper hasn't populated `starters`
    yet for this roster this week (matchup not started / not yet locked),
    so a client never renders a real-looking zero that is actually just
    "no data yet." Once Sleeper does report starters, a 0.0 points value is
    real (nobody has scored yet) and is reported as such.
    """

    raw_starters = [str(pid or "") for pid in (matchup_entry.get("starters") or [])]
    starter_ids = [pid for pid in raw_starters if pid and pid != "0"]
    if not starter_ids:
        return {
            "real_starters": [],
            "real_points": None,
            "has_live_data": False,
            "real_starters_basis": REAL_LINEUP_BASIS,
            "real_empty_slots": [],
        }

    starters_points = matchup_entry.get("starters_points") or []
    slot_labels = _starter_slot_labels(roster_positions)

    valued_by_id: dict[str, pd.Series] = {}
    if "player_id" in valued.columns:
        matching = valued[valued["player_id"].astype(str).isin(starter_ids)]
        valued_by_id = {str(row["player_id"]): row for _, row in matching.iterrows()}

    # A real Sleeper starter missing from `valued` isn't necessarily a
    # non-player (team DEF): modules.player_eligibility.
    # filter_current_fantasy_players treats a literal "Inactive" status as
    # no-longer-current, so a genuinely rostered, genuinely-starting player
    # can vanish from `valued` entirely — the same gap _matchup_side/
    # _suggested_lineup_split already reinstate for the suggested-lineup
    # view above (see _reinstated_inactive_roster_rows's docstring).
    # Reused here, not reinvented, so both matchup views resolve identity
    # the same way (coridian_, 2026-10-17: a real Sleeper opponent starter —
    # Lamar Jackson, status "Inactive" that week — rendered as "Unknown
    # player"/"FA" here despite resolving fine everywhere else).
    missing_ids = {pid for pid in starter_ids if pid not in valued_by_id}
    reinstated_by_id: dict[str, pd.Series] = {}
    if missing_ids and projection_context is not None:
        reinstated_rows = _reinstated_inactive_roster_rows(
            missing_ids,
            players_lookup=projection_context.players_lookup,
            valued=valued,
            settings=settings,
            score_field=score_field,
        )
        reinstated_by_id = {
            str(rec["player_id"]): pd.Series(rec) for rec in reinstated_rows
        }

    # IDP leagues: a real defender starter resolves from the IDP model so he
    # carries his position (slot eligibility) and value, not an unknown row.
    idp_by_id: dict[str, dict[str, Any]] = {}
    if idp_result and idp_result.get("idp"):
        idp_by_id = {str(e["player_id"]): e for e in idp_result.get("players") or []}

    rows: list[dict[str, Any]] = []
    empty_slots: list[str] = []
    # Indexes run over Sleeper's RAW starters array (empty "0" slots
    # included): `starters_points` is parallel to that raw array, so
    # skipping an empty slot before indexing would hand every later starter
    # his neighbour's points.
    for index, player_id in enumerate(raw_starters):
        slot = slot_labels[index] if index < len(slot_labels) else None
        if not player_id or player_id == "0":
            if slot:
                empty_slots.append(slot)
            continue
        actual_points = starters_points[index] if index < len(starters_points) else None
        row = valued_by_id.get(player_id)
        if row is None:
            row = reinstated_by_id.get(player_id)
        if row is not None:
            rows.append(
                _project_real_starter_row(
                    row, score_field, actual_points, projection_context=projection_context, slot=slot
                )
            )
        elif player_id in idp_by_id:
            entry = idp_by_id[player_id]
            injury = str(entry.get("injury_status") or "")
            rows.append(
                {
                    "player_id": player_id,
                    "name": entry.get("name"),
                    "position": entry.get("family"),
                    "team": entry.get("team"),
                    "age": entry.get("age"),
                    "status": "Active",
                    "injury_status": injury or None,
                    "injury_label": injury.title(),
                    "tier": None,
                    "score": entry.get("value"),
                    "opportunity_label": None,
                    "overall_rating": None,
                    "actual_points": round(float(actual_points), 2) if isinstance(actual_points, (int, float)) else None,
                    "projection": None,
                    "game_started": None,
                    "game_final": None,
                    "game_kickoff_at": None,
                    "game_status": None,
                    "slot": slot,
                }
            )
        else:
            # A real Sleeper starter who isn't in our valued pool and
            # isn't a reinstatable "Inactive" rostered player either — a
            # team DEF (no real player_id identity to resolve) or an id
            # genuinely unknown to Sleeper's own player directory. Still
            # show his real points, just without identity/season-value
            # enrichment. `project_player_week` itself returns
            # `unknown_player` for an id it can't resolve, so this still
            # gets an honest projection status rather than a bare None
            # field.
            # Team defenses (player_id = NFL team abbreviation) get a real
            # label/position/team from the NFL team table; anything else
            # stays unresolved rather than invented.
            defense = team_defense.team_defense_identity(player_id) or {}
            rows.append(
                {
                    "player_id": player_id,
                    "name": defense.get("name"),
                    "position": defense.get("position"),
                    "team": defense.get("team"),
                    "age": None,
                    "status": None,
                    "injury_status": None,
                    "injury_label": "",
                    "tier": None,
                    "score": None,
                    "opportunity_label": None,
                    "overall_rating": None,
                    "actual_points": round(float(actual_points), 2) if isinstance(actual_points, (int, float)) else None,
                    "projection": (
                        _weekly_projection_for_player(
                            player_id,
                            projection_context.week,
                            projection_context.season,
                            players_lookup=projection_context.players_lookup,
                            weekly_stats=projection_context.weekly_stats,
                            defense_strength=projection_context.defense_strength,
                            team_qb_pass_attempts_by_team=projection_context.team_qb_pass_attempts_by_team,
                        )
                        if projection_context is not None
                        else None
                    ),
                    # No resolvable team for this id, so there's no schedule
                    # row to check — unknown, same as `_player_game_state`
                    # returns for any other missing-team case.
                    "game_started": None,
                    "game_final": None,
                    "game_kickoff_at": None,
                    "game_status": None,
                    "slot": slot,
                }
            )
            if defense:
                rows[-1].update(_player_game_state(defense.get("team"), projection_context))

    team_points = matchup_entry.get("points")
    return {
        "real_starters": rows,
        "real_points": round(float(team_points), 2) if isinstance(team_points, (int, float)) else None,
        "has_live_data": True,
        "real_starters_basis": REAL_LINEUP_BASIS,
        "real_empty_slots": empty_slots,
    }


# Sleeper roster_positions spellings -> the slot names
# modules.team_eval.suggest_optimal_lineup assigns, so a suggested starter's
# `slot` and a real starter's `slot` compare directly. Anything unlisted
# (DEF, IDP slots, REC_FLEX) passes through as Sleeper spells it: the
# suggested lineup never fills those, and they're labelled honestly rather
# than folded into a slot they aren't.
_SLEEPER_SLOT_ALIASES = {
    "DST": "DEF",
    "D/ST": "DEF",
    "W/R/T": "FLEX",
    "RB/WR/TE": "FLEX",
    "WR/RB/TE": "FLEX",
    "WRRB_FLEX": "WR/RB",
    "W/R": "WR/RB",
    "RB/WR": "WR/RB",
    "OP": "SUPER_FLEX",
}
_NON_STARTER_ROSTER_POSITIONS = {"BN", "BE", "BENCH", "IR", "TAXI"}


def _canonical_lineup_slot(position: Any) -> str:
    label = str(position or "").strip().upper()
    return _SLEEPER_SLOT_ALIASES.get(label, label)


def _starter_slot_labels(roster_positions: list[Any] | None) -> list[str]:
    """The league's starting slots, in Sleeper's own `starters` order."""

    return [
        _canonical_lineup_slot(pos)
        for pos in (roster_positions or [])
        if str(pos or "").strip() and str(pos or "").strip().upper() not in _NON_STARTER_ROSTER_POSITIONS
    ]


def _real_matchup_comparison(my_side: dict[str, Any], opponent_side: dict[str, Any]) -> dict[str, Any] | None:
    """This week's ACTUAL score comparison, from Sleeper's own live points.

    Only produced once Sleeper has actually populated live data for BOTH
    sides (`has_live_data`) — otherwise there is nothing real to compare yet
    (matchup not started this week), and this deliberately returns None
    rather than synthesizing a fake 0-0 tie.
    """

    if not my_side.get("has_live_data") or not opponent_side.get("has_live_data"):
        return None
    my_points = float(my_side.get("real_points") or 0.0)
    opponent_points = float(opponent_side.get("real_points") or 0.0)
    margin = round(my_points - opponent_points, 2)
    if margin > 0:
        edge = "you"
    elif margin < 0:
        edge = "opponent"
    else:
        edge = "even"
    return {
        "my_points": round(my_points, 2),
        "opponent_points": round(opponent_points, 2),
        "margin": margin,
        "edge": edge,
        "basis": REAL_LINEUP_BASIS,
        "basis_label": REAL_LINEUP_BASIS_LABEL,
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


_SLOT_ELIGIBLE_POSITIONS: dict[str, set[str]] = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "K": {"K"},
    "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "WR/RB": {"RB", "WR"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "DL": {"DL"},
    "LB": {"LB"},
    "DB": {"DB"},
    "IDP_FLEX": {"DL", "LB", "DB"},
}


def _position_edges(my_starters: list[dict[str, Any]], opponent_starters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-position expected-points edge between two lineups.

    Each starter counts at his real position, not his lineup slot (a FLEX
    RB adds to RB), and contributes modules.matchup_win_probability.
    starter_expected_points: his real score once his game has started, this
    week's projection before that. That is the same per-player figure the
    win probability sums. A starter with no usable number is counted in
    `unmodeled`, never as a guessed 0. Sorted strongest edge for you first.
    """

    totals: dict[str, dict[str, Any]] = {}

    def add(starters: list[dict[str, Any]], points_key: str, count_key: str) -> None:
        for starter in starters:
            position = str(starter.get("position") or "").strip().upper()
            if not position:
                continue
            bucket = totals.setdefault(
                position,
                {"my_points": 0.0, "opponent_points": 0.0, "my_count": 0, "opponent_count": 0, "unmodeled": 0},
            )
            bucket[count_key] += 1
            points = matchup_win_probability.starter_expected_points(starter)
            if points is None:
                bucket["unmodeled"] += 1
                continue
            bucket[points_key] += points

    add(my_starters, "my_points", "my_count")
    add(opponent_starters, "opponent_points", "opponent_count")

    edges = [
        {
            "position": position,
            "my_points": round(bucket["my_points"], 1),
            "opponent_points": round(bucket["opponent_points"], 1),
            "edge": round(bucket["my_points"] - bucket["opponent_points"], 1),
            "my_count": bucket["my_count"],
            "opponent_count": bucket["opponent_count"],
            "unmodeled": bucket["unmodeled"],
        }
        for position, bucket in totals.items()
        # A position where no starter on either side is modeled has no real
        # number to compare, only two zeros.
        if bucket["unmodeled"] < bucket["my_count"] + bucket["opponent_count"]
    ]
    edges.sort(key=lambda item: item["edge"], reverse=True)
    return edges


def _move_player_fields(player: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": player.get("player_id"),
        "name": player.get("name"),
        "position": player.get("position"),
        "team": player.get("team"),
        "tier": player.get("tier"),
        "slot": player.get("slot"),
        "points": matchup_win_probability.starter_expected_points(player),
        "projection_status": (player.get("projection") or {}).get("status"),
        "injury_label": player.get("injury_label") or "",
    }


def _benched_reason(player: dict[str, Any]) -> str | None:
    """Why the suggested lineup sits this ACTUAL starter, when it is a hard
    availability fact (bye, ruled out) rather than a value call."""

    if (player.get("projection") or {}).get("status") == "bye_week":
        return "bye_week"
    from modules.rankings import is_ruled_out  # local: same import-cycle guard team_eval uses

    if is_ruled_out(str(player.get("status") or ""), str(player.get("injury_status") or "")):
        return "ruled_out"
    return None


def _suggested_lineup_moves(my_side: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The changes that turn this roster's ACTUAL Sleeper lineup into its
    suggested one, as real one-for-one swaps: "start X (slot) over Y", where
    Y is the player CURRENTLY in that slot and X is eligible for it.

    None when Sleeper hasn't posted an actual lineup yet (nothing to diff).
    Only slots the suggested lineup fills are compared, so a team DEF or an
    IDP slot never produces a phantom move.

    Pairing is by slot eligibility (never list order): each suggested-only
    player is matched to an actual-only starter (or an empty slot) whose
    slot his position can fill, preferring the identical slot. When that
    is impossible directly (a WR must move into the W/R slot because the
    RB slot needs the bench RB), the change is a two-leg chain through a
    player who is already starting: "start X over S" in S's slot, then
    "start S over Y" in Y's slot; both legs carry the same `chain_id`. A
    change that needs a longer chain is not shown rather than shown wrong.

    `gain` is the difference in the two players' expected points (see
    matchup_win_probability.starter_expected_points). A bye-week or
    ruled-out starter counts as 0 because he cannot score; a player with no
    modeled number leaves `gain` None rather than guessed. Gains are exact
    differences (no double counting), so the shown moves sum to suggested
    total minus actual total, to within 0.05 per move of rounding.
    `locked` is True once either player's own game has kicked off, because
    Sleeper no longer allows that swap. FantasyDesk can't set Sleeper
    lineups, so this is a planner and the client says so.
    """

    if not my_side.get("has_live_data"):
        return None

    suggested = list(my_side.get("starters") or [])
    actual = list(my_side.get("real_starters") or [])
    suggested_slots = {str(p.get("slot") or "") for p in suggested if p.get("slot")}
    suggested_ids = {str(p.get("player_id") or "") for p in suggested}
    actual_ids = {str(p.get("player_id") or "") for p in actual}

    def eligible(player: dict[str, Any], slot: str) -> bool:
        return str(player.get("position") or "").upper() in _SLOT_ELIGIBLE_POSITIONS.get(slot, set())

    ins = [p for p in suggested if str(p.get("player_id") or "") not in actual_ids]
    # Targets: the actual-only starters (to be replaced) and empty slots.
    targets: list[dict[str, Any]] = [
        {"slot": str(p.get("slot") or ""), "player": p}
        for p in actual
        if str(p.get("player_id") or "") not in suggested_ids and str(p.get("slot") or "") in suggested_slots
    ]
    targets += [
        {"slot": str(slot), "player": None} for slot in (my_side.get("real_empty_slots") or []) if slot in suggested_slots
    ]
    stayers = [p for p in actual if str(p.get("player_id") or "") in suggested_ids]

    # Maximum matching of suggested-only players to targets by slot
    # eligibility (Kuhn), trying the identical slot first.
    owner: dict[int, int] = {}

    def augment(i: int, seen: set[int]) -> bool:
        order = sorted(range(len(targets)), key=lambda t: targets[t]["slot"] != str(ins[i].get("slot") or ""))
        for t in order:
            if t in seen or not eligible(ins[i], targets[t]["slot"]):
                continue
            seen.add(t)
            if t not in owner or augment(owner[t], seen):
                owner[t] = i
                return True
        return False

    for i in range(len(ins)):
        augment(i, set())
    matched_in = {i: t for t, i in owner.items()}

    def points_of(player: dict[str, Any] | None, *, zero: bool = False) -> float | None:
        if zero:
            return 0.0
        return matchup_win_probability.starter_expected_points(player) if player is not None else None

    def build(
        slot: str,
        starter: dict[str, Any],
        over: dict[str, Any] | None,
        *,
        empty: bool = False,
        chain_id: int | None = None,
    ) -> dict[str, Any]:
        start_fields = _move_player_fields(starter)
        over_fields = _move_player_fields(over) if over is not None else None
        reason = "empty_slot" if empty else (_benched_reason(over) if over is not None else None)
        if over_fields is not None and reason in {"bye_week", "ruled_out"}:
            over_fields["points"] = 0.0
        over_points = 0.0 if empty else (over_fields["points"] if over_fields is not None else None)
        start_points = start_fields["points"]
        gain = (
            round(float(start_points) - float(over_points), 1)
            if start_points is not None and over_points is not None
            else None
        )
        move = {
            "slot": slot,
            "start": start_fields,
            "over": over_fields,
            "over_reason": reason,
            "gain": gain,
            "locked": starter.get("game_started") is True
            or (over is not None and over.get("game_started") is True),
        }
        if chain_id is not None:
            move["chain_id"] = chain_id
        return move

    groups: list[list[dict[str, Any]]] = []
    for i, t in matched_in.items():
        target = targets[t]
        groups.append(
            [build(target["slot"], ins[i], target["player"], empty=target["player"] is None)]
        )

    free_targets = [t for t in range(len(targets)) if t not in owner]
    used_stayers: set[str] = set()
    chain_id = 0
    for i in range(len(ins)):
        if i in matched_in:
            continue
        done = False
        for t in list(free_targets):
            target = targets[t]
            for stayer in stayers:
                sid = str(stayer.get("player_id") or "")
                s_slot = str(stayer.get("slot") or "")
                if sid in used_stayers or not eligible(ins[i], s_slot) or not eligible(stayer, target["slot"]):
                    continue
                chain_id += 1
                used_stayers.add(sid)
                free_targets.remove(t)
                groups.append(
                    [
                        build(s_slot, ins[i], stayer, chain_id=chain_id),
                        build(
                            target["slot"],
                            stayer,
                            target["player"],
                            empty=target["player"] is None,
                            chain_id=chain_id,
                        ),
                    ]
                )
                done = True
                break
            if done:
                break

    def group_key(group: list[dict[str, Any]]) -> tuple[Any, ...]:
        gains = [m["gain"] for m in group]
        total = None if any(g is None for g in gains) else sum(gains)
        return (any(m["locked"] for m in group), total is None, -(total or 0.0))

    groups.sort(key=group_key)
    return [move for group in groups for move in group]


def _matchup_game_state(my_side: dict[str, Any], opponent_side: dict[str, Any]) -> str | None:
    """Where this fantasy week stands, from every real starter's own NFL
    game: "live" while any is in progress, "final" once every known game is
    final, "pregame" before any has kicked off, and "between_games" when
    some are done and the rest haven't started (no LIVE badge then). None
    when no starter's game status is known (lineups not posted, schedule
    missing).
    """

    statuses = [
        starter.get("game_status")
        for side in (my_side, opponent_side)
        for starter in (side.get("real_starters") or [])
        if starter.get("game_status")
    ]
    if not statuses:
        return None
    if "in_progress" in statuses:
        return "live"
    if all(status == "final" for status in statuses):
        return "final"
    if all(status == "scheduled" for status in statuses):
        return "pregame"
    return "between_games"


@app.get("/v1/leagues/{league_id}/live-activity")
@_with_sleeper_as_of
def get_league_live_activity(
    league_id: str = Depends(resolve_league_path_id),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Compact real-score snapshot for the iOS Live Activity / widget.

    Same data and not-ready contract as /matchup (200 + `reason`), trimmed to
    what a lock-screen surface renders (modules.live_activity).
    """

    return live_activity.build_live_activity_snapshot(_build_matchup(league_id, "Dynasty", user))


def _empty_matchup(reason: str, week: int | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "week": week,
        "my_team": None,
        "opponent": None,
        "comparison": None,
        "real_comparison": None,
        "win_probability": None,
        "game_state": None,
        "position_edges": None,
        "suggested_moves": None,
        "basis": SEASON_VALUE_BASIS,
        "basis_label": SEASON_VALUE_BASIS_LABEL,
        "reason": reason,
    }


@app.get("/v1/leagues/{league_id}/matchup")
@_with_sleeper_as_of
def get_league_matchup(
    league_id: str = Depends(resolve_league_path_id),
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    return _build_matchup(league_id, lens, user)


def _build_matchup(
    league_id: str,
    lens: str,
    user: dict[str, Any],
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """This week's head-to-head: two views, side by side, per roster.

    View 1 — REAL current lineup/points (`real_starters` / `real_points` /
    `has_live_data` on each side, `real_comparison` at the top level): pulled
    directly from modules.sleeper.get_matchups' live `/league/{id}/matchups/
    {week}` payload — Sleeper's own `starters` (the player_ids this manager
    ACTUALLY has starting this week), `starters_points` (each one's real
    point total scored so far, live during in-progress games), and `points`
    (the roster's real total). This is genuine already-fetched data that
    used to be discarded entirely — not a projection of any kind.
    `has_live_data` is False when Sleeper hasn't populated a roster's
    starters yet this week (not started / not locked), so a client never
    mistakes "no data yet" for a real 0.

    View 2 — SUGGESTED season-value lineup (`starters` / `season_value_total`
    on each side, `comparison` at the top level, unchanged from before):
    both sides run the SAME modules.team_eval.suggest_optimal_lineup pass, so
    this is an apples-to-apples "best available lineup by season value/
    opportunity" comparison — which may differ from what either manager has
    actually set in Sleeper. No weekly-projection feed and no
    opponent-defense-strength data exist anywhere in this codebase, so this
    view intentionally ranks by season-long signal only
    (SEASON_VALUE_BASIS_LABEL), and each starter's `why` cites only real
    season-form fields (tier, workload/opportunity label, season-value rank
    on that roster, injury tag) — never this week's opponent or expected
    points. A true weekly projection would be a new data source, not a
    relabel of this one.

    Week comes from the league's own `settings.leg` (the same current-week
    field the mobile League screen already reads).

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

    is_external = external_leagues.is_external_league_key(league_id)
    my_roster_id = str(my_roster.get("roster_id") or "")
    if is_external:
        # Imported league: the platform's own week and pairing, in Sleeper's shape
        # (modules.external_matchups). An older imported season has no "this week".
        external_state = _external_week_state(league_id, league)
        if external_state is None:
            return _empty_matchup("no_current_week")
        current_week = int(external_state["week"])
        pair = external_matchups.matchup_entries(league_id, int(my_roster_id), external_state)
        if pair is None:
            return _empty_matchup("bye_week", week=current_week)
        my_entry, opponent_entry = pair
    else:
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

    # Same (league_id, lens)-scoped cache /rankings and friends share — see
    # league_value_settings.build_valued_players_frame_cached's docstring.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if valued.empty:
        return _empty_matchup("no_player_data", week=current_week)

    score_field = league_value_settings.valuation_score_field(lens)

    opponent_roster_id = str(opponent_entry.get("roster_id") or "")
    rosters_by_id = {str(r.get("roster_id") or ""): r for r in sleeper.get_rosters(league_id)}
    opponent_roster = rosters_by_id.get(opponent_roster_id)
    if opponent_roster is None:
        return _empty_matchup("opponent_roster_missing", week=current_week)

    profiles = sleeper.get_league_roster_profiles(league_id) or {}
    # Best-effort, same "fails soft" contract as every other enrichment
    # fetch in this file (e.g. the projection lookup below) — a hiccup
    # fetching Sleeper's raw player directory must never break the real
    # matchup response; it only means a rostered-but-Inactive player can't
    # be reinstated into the suggested lineup this one request.
    try:
        matchup_players_lookup = sleeper.get_players()
    except Exception:
        matchup_players_lookup = {}

    # Built BEFORE _matchup_side (not just _real_current_lineup below):
    # the suggested lineup is THIS week's lineup, so it needs every roster
    # player's projection and bye status, even before Sleeper has locked
    # either side's real starters. Best-effort, same "fails soft" contract
    # as everywhere else in this file.
    projection_context = _build_projection_context(current_week)
    idp_result = _league_idp_result(league_id, league) if settings.get("idp_slots") else None

    my_bench: list[dict[str, Any]] = []
    my_side = _matchup_side(
        my_roster_id,
        my_roster,
        profiles.get(my_roster_id) or {},
        valued,
        settings,
        score_field,
        players_lookup=matchup_players_lookup,
        projection_context=projection_context,
        matchup_entry=my_entry,
        bench_out=my_bench if state is not None else None,
        idp_result=idp_result,
    )
    opponent_side = _matchup_side(
        opponent_roster_id,
        opponent_roster,
        profiles.get(opponent_roster_id) or {},
        valued,
        settings,
        score_field,
        players_lookup=matchup_players_lookup,
        projection_context=projection_context,
        matchup_entry=opponent_entry,
        idp_result=idp_result,
    )
    if not my_side["starters"] and not opponent_side["starters"]:
        return _empty_matchup("empty_roster", week=current_week)

    # Additive: each side's REAL current-week lineup/points from Sleeper's
    # own matchup entry, alongside the (unchanged) suggested season-value
    # lineup already built into my_side/opponent_side above. Each real
    # starter also carries this week's per-game `projection` (point
    # estimate/low/high/confidence/honest status) and a `game_started` flag
    # (modules.nfl_schedule's real kickoff time for his team/week) —
    # computed from data fetched ONCE for the whole request (both rosters),
    # not once per player, via `_ProjectionContext`/`_weekly_projection_for_
    # player`/`_player_game_state`.
    roster_positions = league.get("roster_positions") if isinstance(league.get("roster_positions"), list) else []
    my_side.update(
        _real_current_lineup(
            my_entry,
            valued,
            score_field,
            projection_context=projection_context,
            settings=settings,
            # Imported leagues label each starter with the platform's own slot
            # (MFL sends none: no label, never a guessed one).
            roster_positions=my_entry["slot_labels"] if is_external else roster_positions,
            idp_result=idp_result,
        )
    )
    opponent_side.update(
        _real_current_lineup(
            opponent_entry,
            valued,
            score_field,
            projection_context=projection_context,
            settings=settings,
            roster_positions=opponent_entry["slot_labels"] if is_external else roster_positions,
            idp_result=idp_result,
        )
    )
    unmapped_players: list[dict[str, Any]] = []
    if is_external:
        for side, entry in ((my_side, my_entry), (opponent_side, opponent_entry)):
            side["real_empty_slots"] = list(entry.get("empty_slots") or [])
            unmapped_players.extend(entry.get("unmapped") or [])

    # Live, single-week win probability — built from each side's REAL
    # current-week starters (real points once a game's started, this
    # week's per-game projection otherwise), not the hypothetical
    # suggested-optimal lineup. coridian_: "we need ... a bar saying whos
    # winnig/ projected to win ... a live updating predictor." Honestly
    # unavailable (not a guessed 50/50) when either side's starters aren't
    # modeled enough yet — see modules.matchup_win_probability's own
    # docstring for the coverage gate.
    win_probability = matchup_win_probability.compute_live_win_probability(
        my_side.get("real_starters") or [], opponent_side.get("real_starters") or []
    )
    if unmapped_players:
        # A starter we could not match to a FantasyDesk player has no projection, so
        # any odds would silently leave a real scorer out. Say so instead.
        win_probability = {"available": False, "reason": "unmapped_starters"}
    if state is not None:
        state.update(my_side=my_side, opponent_side=opponent_side, my_bench=my_bench, league=league)

    response = {
        "ok": True,
        "week": current_week,
        "my_team": my_side,
        "opponent": opponent_side,
        "comparison": _matchup_comparison(
            my_side["season_value_total"], opponent_side["season_value_total"]
        ),
        "real_comparison": _real_matchup_comparison(my_side, opponent_side),
        "win_probability": win_probability,
        "game_state": _matchup_game_state(my_side, opponent_side),
        # Per-position expected-points edges for each lineup view. `actual`
        # is null until both sides have a real Sleeper lineup posted.
        "position_edges": {
            "actual": (
                _position_edges(my_side["real_starters"], opponent_side["real_starters"])
                if my_side.get("has_live_data") and opponent_side.get("has_live_data")
                else None
            ),
            "suggested": _position_edges(my_side["starters"], opponent_side["starters"]),
        },
        "suggested_moves": None if league_calendar.is_best_ball(league) else _suggested_lineup_moves(my_side),
        "basis": SEASON_VALUE_BASIS,
        "basis_label": SEASON_VALUE_BASIS_LABEL,
        "reason": "",
        # Best ball: Sleeper sets lineups itself, so clients hide the
        # suggested-lineup/start-sit sections (modules.league_calendar).
        "best_ball": league_calendar.is_best_ball(league),
        "lineup_advice_message": (
            league_calendar.BEST_BALL_LINEUP_MESSAGE if league_calendar.is_best_ball(league) else ""
        ),
    }
    if is_external:
        response["platform"] = external_leagues.league_platform(league_id)
        response["unmapped_players"] = unmapped_players
    return response


class MatchupWhatIfLineupSlot(BaseModel):
    slot: str
    player_id: str | None = None


class MatchupWhatIfRequest(BaseModel):
    """A proposed lineup for the user's own side, slot by slot. `edit_index`
    (an index into `lineup`) additionally asks for every candidate swap into
    that slot with its pros and cons."""

    lineup: list[MatchupWhatIfLineupSlot] = Field(default_factory=list, max_length=40)
    edit_index: int | None = None
    lens: str = "Dynasty"


@app.post("/v1/leagues/{league_id}/matchup/what-if")
def post_league_matchup_what_if(
    request: MatchupWhatIfRequest,
    league_id: str = Depends(require_league_access),
    user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Lineup planner: re-score an edited lineup against this week's opponent.

    Planner only; FantasyDesk can't change a Sleeper lineup. Gated exactly
    like GET .../matchup (signed in, no Pro check; the Matchup page is free),
    and ESPN leagues are refused by _EspnLeagueRouteGate. Best ball leagues
    set their own lineups, so the planner answers `reason: best_ball`.

    Rebuilds the page's context through the same `_build_matchup` (cached
    valued frame, shared projections), so the win probability here is the
    scoreboard's `compute_live_win_probability` over the same player rows:
    submitting the Actual lineup returns the scoreboard's number exactly.
    The opponent is their Sleeper lineup when posted, else their suggested
    one. The roster pool is the user's suggested starters, bench and
    Sleeper starters; client-sent player data is never trusted, only ids.
    """

    if request.lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(status_code=422, detail="Unknown lens.")
    state: dict[str, Any] = {}
    page = _build_matchup(league_id, request.lens, user, state)
    if not page.get("ok") or not state:
        return {"ok": False, "reason": page.get("reason") or "no_matchup_data"}
    if page.get("best_ball"):
        return {"ok": True, "reason": "best_ball", "best_ball": True}

    my_side = state["my_side"]
    opponent_side = state["opponent_side"]
    pool: dict[str, dict[str, Any]] = {}
    for group in (my_side.get("starters") or [], state["my_bench"], my_side.get("real_starters") or []):
        for player in group:
            player_id = str(player.get("player_id") or "")
            if player_id and player_id not in pool:
                pool[player_id] = player

    lineup = [{"slot": e.slot, "player_id": e.player_id or None} for e in request.lineup]
    try:
        matchup_what_if.validate_lineup(pool, lineup, _SLOT_ELIGIBLE_POSITIONS)
    except matchup_what_if.LineupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    opponent_starters = (
        opponent_side.get("real_starters") if opponent_side.get("has_live_data") else opponent_side.get("starters")
    ) or []
    evaluated = matchup_what_if.evaluate(pool, lineup, opponent_starters)
    response: dict[str, Any] = {
        "ok": True,
        "reason": "",
        "lineup": evaluated["starters"],
        "win_probability": evaluated["win_probability"],
        "position_edges": _position_edges(evaluated["starters"], opponent_starters),
        "candidates": None,
    }
    if request.edit_index is not None:
        if not 0 <= request.edit_index < len(lineup):
            raise HTTPException(status_code=422, detail="edit_index is outside the lineup.")
        response["candidates"] = matchup_what_if.candidates_for_slot(
            pool, lineup, request.edit_index, opponent_starters, _SLOT_ELIGIBLE_POSITIONS
        )
    return response


_NON_SKILL_WAIVER_POSITIONS = {"K", "DEF", "DST"}


def _secondary_waiver_sections(
    free_agents: pd.DataFrame, priority_ids: set[str], score_field: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stash Candidates / Watchlist Depth / FAAB Shortlist frames.

    Kickers and defenses are never stash candidates (their "upside" is not a
    dynasty asset; an under-24 kicker used to top the list on raw value), and
    in the watchlist and FAAB shortlist they rank below skill players.
    """
    positions = free_agents["position"].fillna("").astype(str).str.upper()
    is_non_skill = positions.isin(_NON_SKILL_WAIVER_POSITIONS)
    pid = free_agents["player_id"].astype(str)
    age_numeric = pd.to_numeric(free_agents.get("age"), errors="coerce").fillna(99)
    upside_labels = {"Backup With Upside", "Starter At Risk", "Committee Back"}
    opportunity = free_agents.get("opportunity_label", pd.Series("", index=free_agents.index)).fillna("")
    stash_mask = ((age_numeric <= 24) | opportunity.isin(upside_labels)) & ~is_non_skill
    stash_df = free_agents[stash_mask & ~pid.isin(priority_ids)].drop_duplicates(subset=["player_id"]).head(6)
    seen_after_stash = priority_ids | set(stash_df["player_id"].astype(str))
    # Stable partition: skill players first, K/DEF only as a fallback.
    ordered = free_agents.loc[list(free_agents.index[~is_non_skill]) + list(free_agents.index[is_non_skill])]
    watchlist_df = ordered[~ordered["player_id"].astype(str).isin(seen_after_stash)].head(6)
    seen_after_watchlist = seen_after_stash | set(watchlist_df["player_id"].astype(str))
    score = pd.to_numeric(free_agents[score_field], errors="coerce").fillna(0)
    faab_pool = free_agents[
        (~free_agents["stale_free_agent"]) & (score > 0) & (~pid.isin(seen_after_watchlist))
    ]
    faab_pool = faab_pool.assign(_non_skill=faab_pool["position"].fillna("").astype(str).str.upper().isin(_NON_SKILL_WAIVER_POSITIONS))
    faab_df = faab_pool.sort_values(["_non_skill", score_field], ascending=[True, False]).drop(columns="_non_skill").head(4)
    return stash_df, watchlist_df, faab_df


def _project_waiver_row(
    row: pd.Series,
    score_field: str,
    opponent_by_team: dict[str, dict[str, Any]] | None = None,
    defense_strength_by_position: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    matchup = (opponent_by_team or {}).get(str(row.get("team") or ""))
    opponent_team = matchup.get("opponent") if matchup else None
    defense_entry = ((defense_strength_by_position or {}).get(str(opponent_team or "")) or {}).get(
        str(row.get("position") or "")
    )
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
        "opponent": opponent_team,
        "opponent_is_home": matchup.get("is_home") if matchup else None,
        # Matchup-difficulty tier for this free agent's upcoming opponent AT
        # THEIR POSITION — modules.player_projections.
        # team_defense_points_allowed_by_position, reused exactly as the
        # Matchup endpoint (get_league_matchup, above) already calls it,
        # same (season, upto_week) shape. Per coridian_'s connectivity-audit
        # finding: this screen already showed the opponent but not whether
        # it's actually a good/bad matchup, even though this exact signal
        # was already computed in this file for a different endpoint.
        # Same "never overweighted" contract as opponent/opponent_is_home
        # above — context only, never touches score/position_rank/
        # overall_rank. Null whenever there's no opponent, no sampled data
        # for that opponent/position, or too few sampled games for a
        # reliable tier (see that function's own docstring).
        "opponent_defense_tier": (defense_entry or {}).get("tier"),
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
        # Sleeper's GLOBAL trending-add signal — cross-league, last-24h add
        # velocity across all of Sleeper, NOT scoped to this league (see
        # waivers_logic.annotate_sleeper_trending_add). sleeper_trending_add_rank
        # is 1-indexed within that global list (1 = most added platform-wide).
        "sleeper_trending_add": bool(row.get("sleeper_trending_add") or False),
        "sleeper_trending_add_count": _clean_json_value(row.get("sleeper_trending_add_count")),
        "sleeper_trending_add_rank": _clean_json_value(row.get("sleeper_trending_add_rank")),
        # 0-99 "OVR" badge — see player_quick_view.overall_ratings_for_pool.
        # Percentiled against the full league-eligible pool (attached to
        # `valued` in get_league_waivers before the free-agent-only filter
        # below), NOT the free-agent-only pool `position_rank`/`overall_rank`
        # above use — a wire-relative rank among only the leftover free
        # agents would rate every free agent far too generously against the
        # true, rostered-players-included position pool the hero ring uses.
        "overall_rating": _clean_json_value(row.get("_overall_rating_col")),
    }


def _project_priority_add(
    row: pd.Series,
    score_field: str,
    guidance: "faab.FaabGuidance",
    opponent_by_team: dict[str, dict[str, Any]] | None = None,
    defense_strength_by_position: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    projected = _project_waiver_row(row, score_field, opponent_by_team, defense_strength_by_position)
    position_rank = int(row.get("position_rank") or 99) or 99
    label, tone = waivers_logic.waiver_recommendation_label(row, position_rank)
    projected["recommendation_label"] = label
    projected["recommendation_tone"] = tone
    # Real need-fit/standout-value confidence for this Priority Add — same
    # already-computed signals rank_priority_add_candidates used to rank it
    # (see waivers_logic.waiver_confidence_label), shown with Trade Ideas'
    # High/Medium/Low confidence language rather than no signal at all.
    confidence_label, confidence_reason = waivers_logic.waiver_confidence_label(row, position_rank)
    projected["confidence_label"] = confidence_label
    projected["confidence_reason"] = confidence_reason
    # Always an object (never null) so installed app builds that read
    # faab.dollars_known unconditionally keep rendering; new clients check
    # `applicable` and show `why` / claim guidance instead of dollars.
    projected["faab"] = {
        "low_bid": guidance.low_bid,
        "high_bid": guidance.high_bid,
        "pct_low": guidance.pct_low,
        "pct_high": guidance.pct_high,
        "remaining": guidance.remaining,
        "dollars_known": guidance.dollars_known,
        "label": guidance.as_label(),
        "applicable": guidance.applicable,
        "waiver_mode": guidance.waiver_mode,
        "why": guidance.why,
        "reasons": list(guidance.reasons),
        "data_confidence": guidance.data_confidence,
    }
    return projected


def _waivers_team_defense_context(settings: dict[str, Any], roster_player_ids: Any) -> dict[str, Any]:
    """Honest D/ST context for Waivers: slot count, the rostered D/ST (real
    identity only) and whether a D/ST slot is unfilled. No ranking, no
    valuations, no waiver recommendation."""

    slots = int(settings.get("def_count") or 0)
    rostered = [
        {**identity, "player_id": pid}
        for pid in sorted({str(p) for p in (roster_player_ids or ())})
        for identity in [team_defense.team_defense_identity(pid)]
        if identity
    ]
    return {
        "slots": slots,
        "rostered": rostered,
        "empty_slot": bool(slots and len(rostered) < slots),
        "recommendations_supported": False,
    }


@app.get("/v1/leagues/{league_id}/waivers")
@_with_sleeper_as_of
def get_league_waivers(
    league_id: str = Depends(resolve_league_path_id),
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
    needs + injury-replacement context, modules.waivers_logic for the
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

    score_field = league_value_settings.valuation_score_field(lens)
    # The league-wide, asker-independent part of this pipeline (valuation
    # lens, overall-rating percentiles, the stale-free-agent row-wise check,
    # Sleeper trending-add, position/overall ranking) is identical for every
    # caller asking about this (league_id, lens) combo within the same live
    # window, so it's single-flighted + Redis-cached — see
    # modules.waivers_logic.build_waiver_free_agent_pool_cached and the big
    # comment above its private compute function for why only this part
    # (not the per-roster work below) is in the cache boundary.
    valued, free_agents = waivers_logic.build_waiver_free_agent_pool_cached(
        league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
    )
    if valued.empty:
        return {"ok": True, "players": [], "priority_adds": [], "needed_positions": [], "reason": "no_player_data"}
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

    rosters = sleeper.get_rosters(league_id)
    roster_player_map = {
        str(roster.get("roster_id")): tuple(
            str(pid) for pid in (roster.get("players") or []) if pid is not None
        )
        for roster in rosters
        if roster.get("roster_id") is not None
    }

    score_series = pd.to_numeric(free_agents.get(score_field, 0), errors="coerce").fillna(0)
    avg_wire_score = int(score_series.mean()) if len(score_series) else 0

    roster_id = str(my_roster.get("roster_id") or "")
    roster_player_ids = roster_player_map.get(roster_id, ())
    roster_df = valued[valued["player_id"].astype(str).isin(roster_player_ids)].copy()

    needed_positions: list[str] = []
    injury_positions: set[str] = set()
    # Surfaced in the response below (injured_starters/injury_positions) —
    # already computed here for injury_replacement_fit's own filter, just
    # not previously exposed past this function. Mirrors app.py's own
    # free_agent_injured_starters, the exact count the web Waivers route's
    # "Injury replacement watch is active for ..." caption reads
    # (modules/waivers_logic.py's render_waiver_workspace_sections).
    injured_starters = 0
    if not roster_df.empty:
        lineup_df = suggest_optimal_lineup(roster_df, settings, score_field=score_field)
        team_needs = trade_analyzer_fit.build_team_needs_assessment(
            roster_df, None, settings, lineup_df=lineup_df, score_field=score_field
        )
        needed_positions = trade_analyzer_fit.get_needed_positions(
            roster_df, None, settings, include_fallback=False, assessment=team_needs
        )
        injury_context = trade_analyzer_fit.roster_injury_context(
            roster_df, lineup_df, taxi_player_ids=my_roster.get("taxi")
        )
        injury_positions = {
            str(pos).upper()
            for pos in (injury_context.get("injury_need_positions") or set())
            if str(pos).upper() in {"QB", "RB", "WR", "TE", "K"}
        }
        injured_starters = int(injury_context.get("injured_starters") or 0)
        if league_calendar.is_best_ball(league):
            # Best ball: Sleeper auto-starts the best scorers each week, so an
            # injured "starter" is covered by roster depth automatically —
            # there's no lineup slot to fill off the wire. Waiver needs fall
            # back to genuine roster-construction needs only.
            injury_positions = set()
        # coridian_, 2026-10-18: "this says current need none when i
        # beluve i have needs for my team" — get_needed_positions(...,
        # include_fallback=False) only returns strict true_needs, which
        # excludes a position with an injured starter whose backup still
        # clears the weekly-coverage bar (temporary_injury_pressure, not
        # a true_need). Dashboard/GM Plan's "Biggest Team Need" tile uses
        # select_need_headline, a broader priority ladder that DOES
        # surface injury pressure — union it in here so Waivers' "Current
        # need" (and Priority Adds ranking, which also reads this list)
        # match what the user already sees elsewhere in the app.
        needed_positions = sorted(set(needed_positions) | injury_positions)

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
    # Matchup-difficulty tier for each free agent's upcoming opponent AT
    # THEIR POSITION — modules.player_projections.
    # team_defense_points_allowed_by_position, reused exactly as the
    # Matchup endpoint (get_league_matchup, above) already calls it, same
    # (season, upto_week) shape. Per coridian_'s connectivity-audit finding:
    # this endpoint already surfaced the opponent but never whether it's
    # actually a good/bad matchup, even though this exact signal was
    # already computed in this file for a different endpoint. Context
    # only, same "never overweighted" contract as opponent_by_team below —
    # never touches score_field, position_rank, or overall_rank anywhere.
    defense_strength_by_position: dict[str, dict[str, dict[str, Any]]] = {}
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
        # Best-effort, same "fails soft" contract as every other enrichment
        # fetch in this file (e.g. the matchup loop just above, and
        # _ProjectionContext's own try/except for the Matchup endpoint): a
        # hiccup fetching Sleeper's season stats must never break the real
        # waiver-pool response, it only means opponent_defense_tier stays
        # null for this request.
        try:
            defense_players_lookup = sleeper.get_players()
            defense_weekly_stats = sleeper.get_season_player_stats(season=season, retain_weekly=True)
            defense_strength_by_position = player_projections.team_defense_points_allowed_by_position(
                season,
                upto_week=current_week - 1,
                weekly_stats=defense_weekly_stats,
                players=defense_players_lookup,
            )
        except Exception:
            defense_strength_by_position = {}

    limited = free_agents.head(max(1, min(limit, 300)))
    players = [
        _project_waiver_row(row, score_field, opponent_by_team, defense_strength_by_position)
        for _, row in limited.iterrows()
    ]

    priority_df = waivers_logic.rank_priority_add_candidates(
        free_agents,
        score_field=score_field,
        needed_positions=needed_positions,
        league_settings=settings,
        roster_df=roster_df,
        max_items=6,
        league=league,
        rosters=rosters,
    )
    faab_budget = faab.sleeper_faab_budget_context(league, rosters, roster_id=roster_id)
    # Sleeper settings.waiver_type: only FAAB leagues (2) get dollar bids;
    # rolling / reverse-standings leagues get claim guidance instead.
    waiver_mode = faab.sleeper_waiver_mode(league)
    faab_enabled = faab.league_uses_faab(league)
    # Full bid context the endpoint previously never passed: starter status,
    # rival need + budgets, wire depth, catalysts, week, strategy, min bid.
    try:
        trending_adds = sleeper.trending_add_rank_map(lookback_hours=24, limit=50)
    except Exception:
        trending_adds = {}
    faab_market = faab.build_faab_market(
        league=league,
        rosters=rosters,
        my_roster_id=roster_id,
        valued=valued,
        score_field=score_field,
        free_agents=free_agents,
        trending_adds=trending_adds,
    )
    faab_strategy = ""
    try:
        stance_strategy, stance_is_set = _fetch_gm_stance_with_set_flag(
            config, str(user.get("_access_token") or ""), user_id=user_id, league_id=league_id
        )
        if stance_is_set:
            faab_strategy = stance_strategy
    except Exception:
        faab_strategy = ""
    faab_season_stats: dict[str, Any] = {}
    if current_week > 0:
        try:
            faab_season_stats = sleeper.get_season_player_stats(
                season=sleeper.default_player_stats_season(), retain_weekly=True
            )
        except Exception:
            faab_season_stats = {}
    priority_adds: list[dict[str, Any]] = []
    for _, row in priority_df.iterrows():
        guidance = faab.faab_guidance_for_free_agent(
            row,
            score_field=score_field,
            league_settings=settings,
            waiver_mode=waiver_mode,
            market=faab_market,
            budget_initial=faab_budget.initial,
            remaining_budget=faab_budget.remaining,
            needed_positions=needed_positions,
            min_bid=faab.sleeper_min_bid(league),
            week=current_week or None,
            team_strategy=faab_strategy,
            season_stats=faab_season_stats,
            best_ball=league_calendar.is_best_ball(league),
        )
        priority_adds.append(
            _project_priority_add(row, score_field, guidance, opponent_by_team, defense_strength_by_position)
        )

    # Secondary waiver board (Stash Candidates / Watchlist Depth / FAAB
    # Shortlist) — matches web's Premium-only gate (modules/waivers_logic.py:
    # "if not is_premium: render_premium_lock(...); return", app.py's
    # classification just above that call). Adapted, not a byte-for-byte
    # port: web dedupes against its own `featured_free_agents` presentation
    # slice, which isn't reproduced here — this dedupes against the same
    # Priority Adds list this endpoint already returns instead.
    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)
    stash_candidates: list[dict[str, Any]] = []
    watchlist_candidates: list[dict[str, Any]] = []
    faab_targets: list[dict[str, Any]] = []
    if is_premium and not free_agents.empty:
        priority_ids = {str(row.get("player_id")) for _, row in priority_df.iterrows()}
        stash_df, watchlist_df, faab_df = _secondary_waiver_sections(free_agents, priority_ids, score_field)

        stash_candidates = [
            _project_waiver_row(row, score_field, opponent_by_team, defense_strength_by_position)
            for _, row in stash_df.iterrows()
        ]
        watchlist_candidates = [
            _project_waiver_row(row, score_field, opponent_by_team, defense_strength_by_position)
            for _, row in watchlist_df.iterrows()
        ]
        faab_targets = [
            _project_waiver_row(row, score_field, opponent_by_team, defense_strength_by_position)
            for _, row in faab_df.iterrows()
        ]

    return {
        "ok": True,
        "players": players,
        # Additive: unrostered defenders, IDP leagues only ([] otherwise).
        "idp_players": _waivers_idp_rows(league_id, league, rosters),
        # Additive, deliberately minimal: team defenses are not in the valued
        # pool, so there is no free-agent D/ST ranking or recommendation.
        # Only the real facts: the league's D/ST slot count and which D/ST
        # (if any) this roster already holds.
        "team_defense": _waivers_team_defense_context(settings, roster_player_ids),
        "priority_adds": priority_adds,
        "needed_positions": needed_positions,
        "available_count": int(len(free_agents)),
        "avg_wire_score": avg_wire_score,
        # Additive (web-next Waivers, Revision 4): already computed above
        # for injury_replacement_fit's own filter, now exposed so a caller
        # can show the same "Injury replacement watch is active for ...,
        # carrying N injured starters" framing web's Streamlit route shows,
        # without re-deriving roster_injury_context client-side.
        "injured_starters": injured_starters,
        "injury_positions": sorted(injury_positions),
        "best_ball": league_calendar.is_best_ball(league),
        # coridian_, 2026-10-18: "our backend can read current ffa
        # balance! ... i think we set it up just assuming it couldnt
        # read that info" — faab_budget (Sleeper's authoritative
        # settings.waiver_budget / waiver_budget_used, modules/faab.py)
        # was already computed above for each priority-add's own FAAB
        # guidance but never surfaced as its own field.
        "faab_remaining": faab_budget.remaining if faab_enabled else None,
        "faab_initial": faab_budget.initial if faab_enabled else None,
        # "faab" | "rolling" | "reverse_standings" | "unknown" (Sleeper
        # settings.waiver_type). Non-FAAB leagues carry no dollar bids.
        "waiver_mode": waiver_mode,
        "faab_enabled": faab_enabled,
        "stash_candidates": stash_candidates,
        "watchlist_candidates": watchlist_candidates,
        "faab_targets": faab_targets,
        "entitlement": {"is_premium": is_premium},
        "reason": "",
    }


# Mobile-only reveal mechanic: watching a rewarded ad temporarily raises the
# Free-tier visible count above modules.trade_hub_presentation.FREE_VISIBLE_IDEAS (2),
# same board/ranking as web. Web has no ad path, so this bonus is layered on
# top of the shared engine rather than added to trade_hub_presentation itself.
AD_BONUS_IDEAS_PER_UNLOCK = 2
MAX_AD_UNLOCKS = 3


def _free_trade_idea_cap(user_id: str, *, claimed_ad_unlocks: int | None = None) -> tuple[int, int]:
    """(ad_unlocks_applied, pool_cap) for a Free user, from SERVER state.

    Paywall audit, 2026-10: `ad_unlocks` / `shown_count` used to be trusted
    straight from the query string, so a Free caller could pass
    `ad_unlocks=3` for 8 ideas (or `shown_count=0` on every All Trades page)
    and every page counted its own allowance. Now ONE per-user pool
    (modules.free_tier_ledger) is shared by Trade Hub, All Trades, the
    Dashboard headline and share cards; the client's ad count is only a
    hint that can raise the server's own count by one per cooldown."""

    if claimed_ad_unlocks is None:
        applied = min(free_tier_ledger.ad_unlocks_granted(user_id), MAX_AD_UNLOCKS)
    else:
        applied = free_tier_ledger.grant_ad_unlock_if_claimed(user_id, claimed_ad_unlocks, MAX_AD_UNLOCKS)
    return applied, trade_hub_presentation.FREE_VISIBLE_IDEAS + AD_BONUS_IDEAS_PER_UNLOCK * applied


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
    ranked_records = trade_hub_presentation.order_trade_hub_visible_ideas(list(records))
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


# `strategy=auto` on GET .../trade-hub: derive the strategy server-side from the
# caller's declared Team Situation instead of making the client fetch it first.
TRADE_HUB_AUTO_STRATEGY = "auto"


@app.get("/v1/leagues/{league_id}/trade-hub")
@_with_sleeper_as_of
def get_trade_hub_ideas(
    league_id: str = Depends(resolve_league_path_id),
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
    contract (modules.trade_hub_presentation.order_trade_hub_visible_ideas /
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

    # Past Sleeper's settings.trade_deadline the board stops pushing
    # in-season trades (modules.league_calendar). Trade Analyzer stays open
    # for offseason planning; this only gates idea generation.
    trade_window = league_calendar.trade_window(league)
    if trade_window["trade_deadline_passed"]:
        return {
            "ok": True,
            "ideas": [],
            "reason": league_calendar.TRADE_DEADLINE_PASSED_REASON,
            "message": league_calendar.TRADE_DEADLINE_PASSED_MESSAGE,
            "trade_window": trade_window,
            "hold": trade_hub_engine.build_hold_verdict([], trade_window=trade_window),
        }

    gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
        config, user_id, str(user.get("_access_token") or ""), league_id
    )
    declared_team_stance = _fetch_team_stance(
        config, user_id, str(user.get("_access_token") or ""), league_id
    )
    if strategy == TRADE_HUB_AUTO_STRATEGY:
        # The caller asked for the strategy this server derives from the
        # declared Team Situation (the same mapping GET .../team-stance
        # returns as `strategy`), so it needs no stance round trip first.
        strategy = team_stance.team_strategy_for_stance(declared_team_stance)
    records = trade_hub_engine.generate_trade_idea_records_cached(
        league_id=league_id,
        roster_id=int(roster_id),
        strategy=strategy,
        lens=lens,
        players_db_path=PLAYERS_DB_PATH,
        untouchable_player_ids=gm_untouchable_ids,
        gm_target_player_ids=gm_target_ids,
        team_stance=declared_team_stance,
        keeper_round_penalty=_trade_idea_keeper_round_penalty(user, league_id),
    )

    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)
    ranked = _project_and_enrich_trade_idea_cards(records, league_id=league_id, lens=lens)
    approved_count = len(ranked)
    if is_premium:
        ad_unlocks_applied = max(0, min(int(ad_unlocks or 0), MAX_AD_UNLOCKS))
        visible = ranked
    else:
        ad_unlocks_applied, pool_cap = _free_trade_idea_cap(user_id, claimed_ad_unlocks=ad_unlocks)
        allowed_ids = free_tier_ledger.claim_trade_ideas(
            user_id, [str(card.get("recommendation_id") or "") for card in ranked], pool_cap
        )
        visible = [card for card in ranked if str(card.get("recommendation_id") or "") in allowed_ids][:pool_cap]
    # Hold verdict: judged on the full approved board (not the free-tier slice)
    # using one already-cached rankings row; no extra idea search.
    power_rank = team_count = None
    try:
        frame = league_rankings.build_league_rankings_frame_cached(
            league_id=league_id, lens=lens, players_db_path=PLAYERS_DB_PATH
        )
        if not frame.empty:
            team_count = int(len(frame))
            mine = frame[frame["roster_id"].astype(str) == str(roster_id)]
            if not mine.empty:
                power_rank = int(mine.iloc[0].get("power_rank"))
    except Exception:
        power_rank = team_count = None
    hold = trade_hub_engine.build_hold_verdict(
        ranked,
        strategy=strategy,
        power_rank=power_rank,
        team_count=team_count,
        season_progress=record_signal.season_progress_fraction(league),
        in_season=league_calendar.is_in_season(league),
        trade_window=trade_window,
    )
    return {
        "ok": True,
        "ideas": visible,
        "reason": "",
        "hold": hold,
        "posture_sentence": trade_hub_engine.posture_sentence(strategy),
        # Logic/valuation audit, 2026-10-18: Trade Hub applies a team-
        # strategy age-curve adjustment (modules.trade_hub_engine.
        # apply_strategy_age_curve, inside generate_trade_idea_records_cached
        # above) that Waivers/Dashboard/PQV's plain valuation pipeline
        # doesn't — so the same player's value can read differently here
        # than elsewhere, with nothing in the UI explaining why. Exposing
        # the effective strategy so the client can label it, instead of
        # silently showing a number that just looks inconsistent.
        "team_strategy": strategy,
        "trade_window": trade_window,
        "entitlement": {
            "is_premium": is_premium,
            "approved_count": approved_count,
            "visible_count": len(visible),
            "hidden_count": approved_count - len(visible),
            "free_limit": trade_hub_presentation.FREE_VISIBLE_IDEAS,
            "ad_bonus_per_unlock": AD_BONUS_IDEAS_PER_UNLOCK,
            "max_ad_unlocks": MAX_AD_UNLOCKS,
            "ad_unlocks_applied": ad_unlocks_applied,
        },
    }


@app.get("/v1/leagues/{league_id}/trade-hub/{recommendation_id}/share-card.png")
def get_trade_hub_idea_share_card(
    recommendation_id: str,
    league_id: str = Depends(resolve_league_path_id),
    strategy: str = "retool",
    lens: str = "Dynasty",
    user: dict[str, Any] = Depends(require_user),
) -> Response:
    """Branded, QR-coded share PNG for one Trade Hub idea.

    The gap this closes: web-next's ShareTradeButton (TradeIdeaCard.tsx)
    only ever called navigator.share({text, title}) with no image
    attached at all — even though modules.share_recommendation_cards /
    modules.share_card_renderer (the exact PNG+QR+branding pipeline the
    legacy Streamlit app already uses for its player-quick-view share
    card, #232) has existed and rendered real branded cards all along.
    This wires that mature pipeline to web-next instead of building a new
    one.

    The idea is re-derived server-side from the SAME cached search
    GET .../trade-hub itself reads (trade_hub_engine.
    generate_trade_idea_records_cached, keyed on league_id/roster_id/
    strategy/lens/untouchables/gm-targets — see that function's own
    docstring) and matched by trade_hub_presentation.idea_recommendation_id, rather
    than trusting any idea payload a client could post — a caller can only
    ever get a branded card for a trade idea this server itself just
    generated for their own roster, never a client-fabricated "trade". If
    the board has since moved on (a stale/no-longer-current
    recommendation_id, or build_trade_share_card otherwise declines it),
    this returns a real 404 with that decline_reason as the error detail,
    never a fabricated image.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    access_token = str(user.get("_access_token") or "")
    profile = _fetch_profile_fields(config, user_id, access_token) if user_id else {}

    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        raise HTTPException(status_code=404, detail=reason or "Roster not found.")

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    roster_id = my_roster.get("roster_id")
    if roster_id is None:
        raise HTTPException(status_code=404, detail="empty_roster")

    gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
        config, user_id, access_token, league_id
    )
    declared_team_stance = _fetch_team_stance(config, user_id, access_token, league_id)
    # Same (league_id, roster_id, strategy, lens, untouchables, gm-targets)
    # key /trade-hub itself reads — this call hits that cache rather than
    # recomputing the search, and crucially re-derives the exact idea set
    # the client's own /trade-hub response was built from.
    records = trade_hub_engine.generate_trade_idea_records_cached(
        league_id=league_id,
        roster_id=int(roster_id),
        strategy=strategy,
        lens=lens,
        players_db_path=PLAYERS_DB_PATH,
        untouchable_player_ids=gm_untouchable_ids,
        gm_target_player_ids=gm_target_ids,
        team_stance=declared_team_stance,
        keeper_round_penalty=_trade_idea_keeper_round_penalty(user, league_id),
    )
    idea = next(
        (record for record in records if trade_hub_presentation.idea_recommendation_id(record) == recommendation_id),
        None,
    )
    # A Free caller may only render a card for an idea already in its own
    # revealed pool (i.e. one it was actually shown) -- the board above is
    # the FULL, unredacted idea set, so without this any hidden idea could be
    # pulled out as a branded PNG by guessing/enumerating recommendation ids.
    if idea is not None and not premium.is_at_least(profile.get("entitlement"), premium.PRO):
        if not free_tier_ledger.is_idea_revealed(user_id, recommendation_id):
            raise HTTPException(status_code=404, detail="Unlock this idea to share it.")

    team_profile = sleeper.get_league_roster_profiles(league_id).get(str(roster_id), {})
    my_team_name = str(team_profile.get("team_name") or "")
    detected_settings = league_value_settings.detect_league_value_settings_from_payload(league)

    card = share_recommendation_cards.build_trade_share_card(
        idea or {},
        source_surface="trade_hub",
        scoring_format=str(detected_settings.get("scoring_format") or ""),
        my_team_name=my_team_name,
    )
    if not card.is_shareable:
        raise HTTPException(
            status_code=404,
            detail=card.decline_reason
            or "This recommendation has changed. Review the latest analysis before sharing.",
        )

    try:
        png = share_card_renderer.render_share_card_png(card)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc) or "This recommendation has changed. Review the latest analysis before sharing.",
        ) from exc

    return Response(content=png, media_type="image/png")


@app.get("/v1/leagues/{league_id}/trade-finder")
def get_trade_finder_ideas(
    league_id: str = Depends(resolve_league_path_id),
    player_ids: str = "",
    strategy: str = "retool",
    lens: str = "Dynasty",
    pick_ids: str = "",
    return_picks: bool = False,
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

    Draft picks: `pick_ids` is a comma-separated list of GET .../draft-picks
    pick_id values ("season:round:original_roster_id") the caller wants to
    offer — players, picks, or both make a valid selection. The engine
    resolves them against only the picks this roster actually owns (Sleeper
    traded-picks data); anything else is dropped, and at most
    trade_ideas.TRADE_FINDER_MAX_SELECTED_PICKS are used. `return_picks=true`
    keeps only packages whose return includes at least one partner pick.
    """

    if lens not in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD:
        raise HTTPException(
            status_code=422,
            detail="lens must be one of: " + ", ".join(league_value_settings.VALUATION_LENS_TO_SCORE_FIELD),
        )

    config = auth_supabase.get_supabase_config()
    user_id = str(user.get("id") or "")
    profile = _fetch_profile_fields(config, user_id, str(user.get("_access_token") or "")) if user_id else {}

    # Trade Finder is Premium-only on app.py (modules.trade_hub_presentation's
    # current_user_is_premium() gate on the whole workspace) — coridian_,
    # 2026-10-17: "streamlit had proper premium bqarriers." Checked before
    # the selected-players validation below since a free user can't use
    # this feature at all, regardless of what they selected.
    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)
    if not is_premium:
        return {"ok": True, "ideas": [], "reason": "", "is_premium": False, "upsell": _TRADE_FINDER_UPSELL}

    selected_ids = tuple(sorted({pid.strip() for pid in player_ids.split(",") if pid.strip()}))
    selected_pick_ids = tuple(dict.fromkeys(pid.strip() for pid in pick_ids.split(",") if pid.strip()))
    if not selected_ids and not selected_pick_ids:
        return {"ok": True, "ideas": [], "reason": "no_players_selected", "is_premium": True, "upsell": None}

    my_roster, reason = _resolve_my_roster(user, league_id, profile=profile)
    if my_roster is None:
        return {"ok": True, "ideas": [], "reason": reason, "is_premium": True, "upsell": None}

    roster_id = my_roster.get("roster_id")
    if roster_id is None:
        return {"ok": True, "ideas": [], "reason": "empty_roster", "is_premium": True, "upsell": None}

    league = sleeper.get_league(league_id) or {}
    trade_window = league_calendar.trade_window(league)
    if trade_window["trade_deadline_passed"]:
        return {
            "ok": True,
            "ideas": [],
            "reason": league_calendar.TRADE_DEADLINE_PASSED_REASON,
            "message": league_calendar.TRADE_DEADLINE_PASSED_MESSAGE,
            "is_premium": True,
            "upsell": None,
            "trade_window": trade_window,
        }

    gm_target_ids, gm_untouchable_ids = _fetch_gm_target_player_ids(
        config, user_id, str(user.get("_access_token") or ""), league_id
    )
    declared_team_stance = _fetch_team_stance(
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
        team_stance=declared_team_stance,
        trade_block_pick_ids=selected_pick_ids,
        require_receive_picks=bool(return_picks),
    )
    ranked = _project_and_enrich_trade_idea_cards(records, league_id=league_id, lens=lens)
    return {
        "ok": True,
        "ideas": ranked,
        "reason": "",
        "is_premium": True,
        "upsell": None,
        "trade_window": trade_window,
    }


@app.get("/v1/leagues/{league_id}/all-trades")
def get_league_all_trades(
    league_id: str = Depends(resolve_league_path_id),
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

    Same free-tier gating as /trade-hub (modules.trade_hub_presentation.
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
    is_premium = premium.is_at_least(profile.get("entitlement"), premium.PRO)

    league = sleeper.get_league(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found.")

    trade_window = league_calendar.trade_window(league)
    if trade_window["trade_deadline_passed"]:
        return {
            "ok": True,
            "ideas": [],
            "has_more": False,
            "next_cursor": max(0, cursor),
            "total_teams": 0,
            "reason": league_calendar.TRADE_DEADLINE_PASSED_REASON,
            "message": league_calendar.TRADE_DEADLINE_PASSED_MESSAGE,
            "trade_window": trade_window,
            "entitlement": {
                "is_premium": is_premium,
                "free_limit": trade_hub_presentation.FREE_VISIBLE_IDEAS,
                "ad_bonus_per_unlock": AD_BONUS_IDEAS_PER_UNLOCK,
                "max_ad_unlocks": MAX_AD_UNLOCKS,
                "ad_unlocks_applied": 0,
                "remaining_free": 0,
            },
        }

    my_roster, _reason = _resolve_my_roster(user, league_id, profile=profile)
    if _reason == FREE_LEAGUE_CAP_REASON:
        return {
            "ok": True,
            "ideas": [],
            "has_more": False,
            "next_cursor": max(0, cursor),
            "total_teams": 0,
            "reason": _reason,
            "entitlement": {
                "is_premium": False,
                "free_limit": trade_hub_presentation.FREE_VISIBLE_IDEAS,
                "ad_bonus_per_unlock": AD_BONUS_IDEAS_PER_UNLOCK,
                "max_ad_unlocks": MAX_AD_UNLOCKS,
                "ad_unlocks_applied": 0,
                "remaining_free": 0,
            },
        }
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
    declared_team_stance = _fetch_team_stance(
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
    # `shown_count` is accepted for old clients but ignored: the allowance
    # is the shared server-side pool, not a client-reported tally.
    if is_premium:
        ad_unlocks_applied = max(0, min(int(ad_unlocks or 0), MAX_AD_UNLOCKS))
        free_cap = 0
        remaining_free = 0
    else:
        ad_unlocks_applied, free_cap = _free_trade_idea_cap(user_id, claimed_ad_unlocks=ad_unlocks)
        remaining_free = max(0, free_cap - free_tier_ledger.pool_size(user_id))

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
                team_stance=declared_team_stance if is_my_roster else "",
                keeper_round_penalty=_trade_idea_keeper_round_penalty(user, league_id),
            )
        except Exception:
            continue
        ranked_records = trade_hub_presentation.order_trade_hub_visible_ideas(list(records))
        # Cap per-team so one roster's board can't eat a whole page —
        # "All Trades" is meant to sample across the league, not repeat
        # Trade Hub's own full-depth board once per team.
        for record in ranked_records[:2]:
            if not is_premium:
                if not free_tier_ledger.claim_trade_ideas(
                    user_id, [trade_hub_presentation.idea_recommendation_id(record)], free_cap
                ):
                    remaining_free = 0
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
                remaining_free = max(0, free_cap - free_tier_ledger.pool_size(user_id))

    next_cursor = cursor + page_size
    return {
        "ok": True,
        "ideas": ideas,
        "has_more": next_cursor < total_teams and (is_premium or remaining_free > 0 or ad_unlocks_applied < MAX_AD_UNLOCKS),
        "next_cursor": next_cursor,
        "total_teams": total_teams,
        "entitlement": {
            "is_premium": is_premium,
            "free_limit": trade_hub_presentation.FREE_VISIBLE_IDEAS,
            "ad_bonus_per_unlock": AD_BONUS_IDEAS_PER_UNLOCK,
            "max_ad_unlocks": MAX_AD_UNLOCKS,
            "ad_unlocks_applied": ad_unlocks_applied,
            "remaining_free": remaining_free,
        },
    }


# Service-to-service editorial export never calls require_user or exposes league/account data.
from services.fantasy_content import content_reader, require_content_token
_content_feed = content_reader(PLAYERS_DB_PATH, _maybe_schedule_players_refresh,
                               lambda: get_news(limit=20, _user={})["items"])

@app.get("/v1/content/feed", dependencies=[Depends(require_content_token)])
def get_public_content_feed():
    return _content_feed()


# Public, anonymous, league-agnostic value board for the SEO pages
# (web-next /dynasty-rankings, /players/[slug], ...). Default 12-team PPR
# dynasty settings only -- never reads a user, league, roster or account.
@app.get("/v1/public/dynasty-values")
def get_public_dynasty_values(format: str = "1qb", tep: bool = False) -> JSONResponse:
    fmt = str(format or "").strip().lower()
    if fmt not in public_dynasty_values.FORMATS:
        raise HTTPException(status_code=422, detail="format must be one of: " + ", ".join(public_dynasty_values.FORMATS))
    payload = public_dynasty_values.get_public_dynasty_values(PLAYERS_DB_PATH, fmt, bool(tep))
    if payload is None:
        raise HTTPException(status_code=503, detail="Dynasty values are not available right now.")
    return JSONResponse(content=payload, headers={"Cache-Control": "public, max-age=300"})
