"""Team Situation — explicit, user-declared GM stance (Decision Memory v1 gap).

NAME COLLISION NOTE: this is unrelated to modules.decision_memory (a
recommendation-CHANGE-HISTORY log). This module stores a single durable,
user-declared value: "how do you see your team right now" — Rebuilding,
Competing, or Balanced. It is a manual declaration, never inferred.

Contract (mirrors modules.gm_targets' Supabase conventions):
  - Durable row keyed by (user_id, league_id) — one stance per user per league
  - RLS fail-closed: auth.uid() = user_id only
  - Streamlit/mobile use anon key + user JWT (no service_role)
  - Fail-open: any Supabase outage/misconfiguration returns "" (no stance),
    never raises, never blocks the app

Team Situation vs. valuation math — merged, 2026-09-26 (coridian_'s product
decision), MOBILE ONLY: this module used to be presentation-only,
appending a clause to trade-idea rationale TEXT via
modules.trade_ideas.apply_team_stance_framing and nothing else. GM Stance
(services/mobile_api_service.py's old "team_strategy_by_league"
user_settings field, five states: contender / fringe_contender / retool /
rebuild / tank — a MOBILE-only feature) was the SEPARATE system with real
teeth there — it fed modules.trade_hub_engine.apply_strategy_age_curve and
strategy_adjusted_pick_score_multiplier, which genuinely rewrite the active
score_field. That separate GM Stance storage is now retired: on mobile,
Team Situation (this module) is the single source of truth, and its
declared value now ALSO drives that same real math, via
team_strategy_for_stance() below (see services/mobile_api_service.py's
_fetch_gm_stance_with_set_flag and the dashboard/trade-hub endpoints).
This module's own storage/read/write functions are unchanged; only the
number of things that now read the stored value grew from one (rationale
framing) to two (rationale framing + real valuation adjustment) — on
mobile. The web app (app.py) has its own, separate, pre-existing
"Strategy" override (modules.profile's strategy_override /
modules.game_plan_truth_canon) that is NOT named GM Stance and is NOT part
of this merge — it keeps driving web valuation independently, unchanged.

"Protect" tags are NOT a new concept here — modules.gm_targets' existing
`untouchable` flag (GmTarget.untouchable) already is exactly that ("never
ship this player away"). This module intentionally has no player-list
storage of its own; the UI layers read/write modules.gm_targets directly.

Graduated: default ON. Kill switch: DYNASTYGM_EXPERIMENTAL_TEAM_STANCE=0
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping

from modules import account_store
from modules import auth_supabase
from modules import experimental_graduation


EXPERIMENT_ENV_KEY = "DYNASTYGM_EXPERIMENTAL_TEAM_STANCE"
STANCE_TABLE = "team_stance"

STANCE_REBUILDING = "rebuilding"
STANCE_COMPETING = "competing"
STANCE_BALANCED = "balanced"
STANCE_OPTIONS: tuple[str, ...] = (STANCE_REBUILDING, STANCE_COMPETING, STANCE_BALANCED)

STANCE_LABELS: dict[str, str] = {
    STANCE_REBUILDING: "Rebuilding",
    STANCE_COMPETING: "Competing",
    STANCE_BALANCED: "Balanced",
}

FEATURE_LABEL = "Team Situation"
# Rendered on web by modules.team_stance_ui — the "mobile app" caveat is
# deliberate: web's own trade valuation is driven by a separate, older
# "Strategy" override (modules.profile / modules.game_plan_truth_canon),
# not by this stance, so this copy must not promise a valuation effect web
# doesn't actually have (GM Stance / Team Situation merge, 2026-09-26).
SUPPORTING_COPY = (
    "Tell us how you see your team right now. We'll lean trade-idea language "
    "toward that stance — and, in the mobile app, use it to shape trade and "
    "lineup value adjustments too."
)

SESSION_CACHE_STANCE_KEY = "_team_stance_cache_value"
SESSION_CACHE_LEAGUE_KEY = "_team_stance_cache_league"
SESSION_HYDRATED_KEY = "_team_stance_hydrated_league"
SESSION_UNAVAILABLE_KEY = "_team_stance_unavailable"


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def normalize_stance(value: object) -> str:
    """Return a canonical stance key, or "" when the value isn't one of the fixed set."""

    key = _safe_text(value).strip().lower()
    return key if key in STANCE_OPTIONS else ""


def stance_label(value: object) -> str:
    return STANCE_LABELS.get(normalize_stance(value), "")


# --- GM Stance merge (product decision, 2026-09-26) ------------------------
#
# GM Stance's five states (contender / fringe_contender / retool / rebuild /
# tank — modules.team_eval.TEAM_STRATEGY_LABELS) drive real valuation math:
# modules.trade_hub_engine.apply_strategy_age_curve's age-curve multiplier
# and strategy_adjusted_pick_score_multiplier's pick-value multiplier, both
# keyed on one of those five concrete strings. Team Situation's three states
# are coarser, so this is an explicit, honest, LOSSY mapping — not a rename.
#
# GM Stance's own modules.team_eval.TEAM_STRATEGY_MODE_MAP already collapses
# its five states into three buckets for other purposes ("contender" /
# "competitive" / "rebuild"). This mapping reuses that exact grouping and
# picks one concrete representative strategy per bucket — the age-curve
# table needs one of the five concrete keys, not the mode label itself:
#   STANCE_COMPETING  -> "contender"  (mode "contender" — the only strategy in it)
#   STANCE_BALANCED   -> "retool"     (mode "competitive" — the more moderate
#                                      of its two strategies; "fringe_contender"
#                                      is the other and is no longer reachable)
#   STANCE_REBUILDING -> "rebuild"    (mode "rebuild" — the more moderate of
#                                      its two strategies; "tank" is the
#                                      other and is no longer reachable)
#   "" (no stance declared) -> "retool", GM Stance's own pre-merge default,
#                               so a user who never declares a Team Situation
#                               sees the exact same valuation as before.
#
# A user who wants GM Stance's more extreme "fringe_contender" or "tank"
# precision no longer has a way to express that — that granularity is
# intentionally gone now that Team Situation (three states) is the only
# control surface for this input.
_STANCE_TO_TEAM_STRATEGY: dict[str, str] = {
    STANCE_COMPETING: "contender",
    STANCE_BALANCED: "retool",
    STANCE_REBUILDING: "rebuild",
}
DEFAULT_TEAM_STRATEGY = "retool"


def team_strategy_for_stance(value: object) -> str:
    """Map a declared Team Situation stance to the GM-Stance-era strategy key
    modules.trade_hub_engine.apply_strategy_age_curve (and
    strategy_adjusted_pick_score_multiplier) expect. "" / unknown input falls
    back to DEFAULT_TEAM_STRATEGY, matching the default those functions used
    before this merge.
    """

    return _STANCE_TO_TEAM_STRATEGY.get(normalize_stance(value), DEFAULT_TEAM_STRATEGY)


def experiment_enabled(*, environ: Mapping[str, str] | None = None) -> bool:
    """Graduated kill switch — default ON; set env to 0/false/off to disable."""

    return experimental_graduation.graduated_kill_switch_enabled(
        EXPERIMENT_ENV_KEY,
        environ=environ,
        default=experimental_graduation.GRADUATED_DEFAULT_ON,
    )


def clear_team_stance_session(state: MutableMapping[str, Any]) -> None:
    """Drop in-memory cache on logout / account / league switch.

    Never deletes durable Supabase rows.
    """

    state.pop(SESSION_CACHE_STANCE_KEY, None)
    state.pop(SESSION_CACHE_LEAGUE_KEY, None)
    state.pop(SESSION_HYDRATED_KEY, None)
    state.pop(SESSION_UNAVAILABLE_KEY, None)


def is_authenticated(session: Mapping[str, Any] | None) -> bool:
    return bool(auth_supabase.current_user_id(dict(session or {})))


def can_access_stance(
    session: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Authenticated users only when the feature is on. No Premium gate — a
    manual declaration is not a durable-history product like Decision Memory."""

    if not experiment_enabled(environ=environ):
        return False
    return is_authenticated(session)


def should_sync_durable(
    session: Mapping[str, Any] | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    if not can_access_stance(session, environ=environ):
        return False
    if bool((session or {}).get(SESSION_UNAVAILABLE_KEY)):
        return False
    return True


def _resolve_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(config, Mapping) and config:
        return dict(config)
    try:
        secrets = None
        try:
            import streamlit as st

            secrets = st.secrets
        except Exception:
            secrets = None
        return auth_supabase.get_supabase_config(secrets=secrets)
    except Exception:
        return {}


def _mark_unavailable(session: MutableMapping[str, Any], error: str = "") -> None:
    session[SESSION_UNAVAILABLE_KEY] = True
    if error:
        session["_team_stance_last_error"] = account_store.customer_safe_error(
            error, context="Team Situation"
        )


def cached_stance(
    session: Mapping[str, Any] | None,
    *,
    league_id: str,
) -> str:
    """Session-cached stance for this league — "" if not hydrated/cached."""

    if not isinstance(session, Mapping):
        return ""
    if _safe_text(session.get(SESSION_CACHE_LEAGUE_KEY)) != _safe_text(league_id):
        return ""
    return normalize_stance(session.get(SESSION_CACHE_STANCE_KEY))


def _cache_stance(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    stance: str,
) -> None:
    league_key = _safe_text(league_id)
    session[SESSION_CACHE_LEAGUE_KEY] = league_key
    session[SESSION_HYDRATED_KEY] = league_key
    session[SESSION_CACHE_STANCE_KEY] = normalize_stance(stance)


def fetch_stance_for_league(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    force: bool = False,
) -> str:
    """Durable stance for this (user, league). "" when unset/unavailable/unauthenticated.

    Fails soft: any Supabase outage or missing table returns "" rather than
    raising — a Team Situation outage must never block Trade Hub or the
    Dashboard from rendering.
    """

    league_key = _safe_text(league_id)
    if not league_key or not should_sync_durable(session, environ=environ):
        return ""

    if (
        not force
        and _safe_text(session.get(SESSION_HYDRATED_KEY)) == league_key
        and _safe_text(session.get(SESSION_CACHE_LEAGUE_KEY)) == league_key
    ):
        return normalize_stance(session.get(SESSION_CACHE_STANCE_KEY))

    user_id = auth_supabase.current_user_id(session)
    access_token = auth_supabase.current_access_token(session)
    if not user_id or not access_token:
        return ""

    resolved = _resolve_config(config)
    if not auth_supabase.is_configured(resolved):
        return ""

    rows, error = account_store.fetch_rows(
        resolved,
        access_token,
        STANCE_TABLE,
        user_id=user_id,
        extra_query=f"league_id=eq.{league_key}&select=stance&limit=1",
        timing_label="team_stance_fetch",
        timeout=8,
    )
    if error:
        if "does not exist" in error.casefold() or "schema cache" in error.casefold():
            _mark_unavailable(session, error)
        return ""

    stance = normalize_stance(rows[0].get("stance")) if rows else ""
    _cache_stance(session, league_id=league_key, stance=stance)
    return stance


def set_stance(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    stance: str,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Upsert the caller's declared stance for this league.

    `stance` must be one of STANCE_OPTIONS; anything else is rejected rather
    than silently coerced, so a typo/garbage value never gets stored and
    silently changes recommendation framing.
    """

    result: dict[str, Any] = {"ok": False, "error": ""}
    if not should_sync_durable(session, environ=environ):
        result["error"] = "Team Situation is not available right now."
        return result

    league_key = _safe_text(league_id)
    stance_key = normalize_stance(stance)
    if not league_key:
        result["error"] = "Select a league first."
        return result
    if not stance_key:
        result["error"] = "Choose Rebuilding, Competing, or Balanced."
        return result

    user_id = auth_supabase.current_user_id(session)
    access_token = auth_supabase.current_access_token(session)
    if not user_id or not access_token:
        result["error"] = "Sign in to save your team situation."
        return result

    resolved = _resolve_config(config)
    payload = {
        "user_id": user_id,
        "league_id": league_key,
        "stance": stance_key,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    ok, error = account_store.upsert_row(
        resolved,
        access_token,
        STANCE_TABLE,
        payload,
        on_conflict="user_id,league_id",
    )
    if not ok:
        if "does not exist" in error.casefold() or "schema cache" in error.casefold():
            _mark_unavailable(session, error)
        result["error"] = account_store.customer_safe_error(error, context="Team Situation")
        return result

    _cache_stance(session, league_id=league_key, stance=stance_key)
    result["ok"] = True
    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            "team_stance_set",
            props=launch_analytics.build_context_props(
                session,
                league_id=league_key,
                source_surface="team_stance",
            ),
            state=session if isinstance(session, dict) else None,
        )
    except Exception:
        pass
    return result
