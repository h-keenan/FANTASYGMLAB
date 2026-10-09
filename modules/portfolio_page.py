"""Web Portfolio page — cross-league standing/needs/opportunities at a glance.

coridian_-approved multi-league view: a single surface showing a user's
standing/needs/opportunities across ALL their connected leagues at once,
previously discussed as a planned Premium feature but never built.

Every row is built by ``modules.dashboard_engine.build_league_summary`` —
the exact same engines (``modules.league_value_settings``,
``modules.trade_hub_engine``, ``modules.league_rankings``,
``modules.injury_ui``, ``dashboard_engine.compose_next_move_briefing``) the
single-league Dashboard already uses — once per saved league, condensed to
a compact row. The mobile API's ``GET /v1/portfolio``
(services/mobile_api_service.py) calls that exact same shared function, so
web and mobile agree on every league's summary. No new valuation or ranking
math lives here, and this module never imports app.py (modules/ never
imports app.py — app.py imports modules/, same rule dashboard_engine.py's
own docstring documents).

Navigation is caller-owned, same convention ``modules.account_ui``'s
``render_account_panel`` already uses: this module never calls into
app.py's league-switch machinery itself. ``render_portfolio_page`` returns
an actions dict; a truthy ``"open_league"`` entry is the saved-league row
the caller should resume (e.g. via app.py's ``_resume_saved_supabase_league``)
and rerun on.
"""

from __future__ import annotations

import concurrent.futures
import functools
from typing import Any, Mapping

import streamlit as st

from modules import (
    account_store,
    auth_supabase,
    dashboard_engine,
    gm_targets,
    premium,
    saved_leagues,
    team_stance,
)
from modules.html_rendering import render_html_fragment
from modules.ui_primitives import content_card_html, empty_state_panel_html, status_badge_html

PAGE_KEY = "portfolio"
NAV_LABEL = "Portfolio"
DEFAULT_LENS = "Dynasty"
PLAYERS_DB_PATH = "data/players.db"

# Bounds the per-request fan-out below — plenty for modules.saved_leagues'
# real-world Premium usage (a handful of leagues) without one request
# opening unboundedly many threads if an account has saved dozens.
PORTFOLIO_FANOUT_MAX_WORKERS = 8

PORTFOLIO_UPSELL_TITLE = "See every league at a glance"
PORTFOLIO_UPSELL_BODY = (
    "Portfolio is a Premium feature — free accounts keep one saved league, "
    "so there's nothing to aggregate yet. Upgrade to Premium to save every "
    "league you're in and see your record, rank, and top need or "
    "opportunity across all of them in one place."
)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _record_label(summary: Mapping[str, Any]) -> str:
    wins = summary.get("wins")
    losses = summary.get("losses")
    if wins is None and losses is None:
        return ""
    ties = summary.get("ties") or 0
    base = f"{int(wins or 0)}-{int(losses or 0)}"
    return f"{base}-{int(ties)}" if ties else base


def _rank_label(summary: Mapping[str, Any]) -> str:
    power_rank = summary.get("power_rank")
    if power_rank is None:
        return ""
    prefix = "T-" if summary.get("power_rank_tied") else "#"
    return f"Roster Power {prefix}{int(power_rank)}"


def _build_portfolio_row(
    session_snapshot: Mapping[str, Any],
    sleeper_username: str,
    entitlement: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    """One saved league's Portfolio row — runs on a worker thread.

    Fans out the exact same three per-league calls the old sequential loop
    made (team_stance, GM Targets, dashboard_engine.build_league_summary) so
    a user with several saved leagues pays the slowest ONE of them instead
    of the sum of all of them.

    Takes a plain-dict `session_snapshot` rather than the live
    `st.session_state`, for two reasons: (1) Streamlit's session state is
    bound to the main script thread — touching it from a worker thread logs
    "missing ScriptRunContext" and isn't supported; (2)
    `team_stance.fetch_stance_for_league` / `gm_targets.fetch_targets_for_league`
    cache onto a SINGLE slot in the session keyed to "whichever league was
    last fetched" (they're built for the single-league Dashboard, not a
    multi-league fan-out) — sharing one live mapping across concurrent
    leagues would let them race and clobber each other's cache slot. Each
    call below gets its OWN fresh copy of the snapshot, so every league's
    cache writes are thread-local and thrown away with it; only the
    returned value (computed from this call's own fresh fetch, never read
    back from that cache slot) is used.
    """

    league_id = saved_leagues.normalize_league_id(row.get("league_id"))
    if not league_id:
        return {"status": "skip"}
    league_name = _safe_text(row.get("league_name"), league_id)
    isolated_session = dict(session_snapshot)

    try:
        team_stance_value = team_stance.fetch_stance_for_league(
            isolated_session, league_id=league_id
        )
        targets = gm_targets.fetch_targets_for_league(isolated_session, league_id=league_id)
        gm_target_ids = tuple(sorted({t.player_id for t in targets}))
        gm_untouchable_ids = tuple(sorted({t.player_id for t in targets if t.untouchable}))
        summary = dashboard_engine.build_league_summary(
            league_id=league_id,
            lens=DEFAULT_LENS,
            sleeper_username=sleeper_username,
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


def render_portfolio_page() -> dict[str, Any]:
    """Render the Portfolio page. Returns `{"open_league": row | None}` —
    see module docstring for how the caller should act on it."""

    actions: dict[str, Any] = {"open_league": None}

    entitlement = premium.get_user_entitlement(session_state=st.session_state)
    if entitlement != premium.PREMIUM:
        premium.render_premium_lock(
            PORTFOLIO_UPSELL_TITLE, PORTFOLIO_UPSELL_BODY, feature="Portfolio"
        )
        return actions

    config = auth_supabase.get_supabase_config()
    user_id = auth_supabase.current_user_id(st.session_state)
    access_token = auth_supabase.current_access_token(st.session_state)
    if not user_id or not access_token:
        render_html_fragment(
            empty_state_panel_html(
                "Sign in to see your Portfolio",
                "Portfolio aggregates your saved leagues, so it needs a signed-in account.",
                kind="unavailable",
            )
        )
        return actions

    saved_rows, error = account_store.fetch_saved_leagues(config, access_token, user_id=user_id)
    if error:
        render_html_fragment(
            empty_state_panel_html(
                "Portfolio is temporarily unavailable",
                account_store.customer_safe_error(error, context="saved_leagues"),
                kind="unavailable",
            )
        )
        return actions

    if not saved_rows:
        render_html_fragment(
            empty_state_panel_html(
                "No saved leagues yet",
                "Save a league to see your standing, record, and top need or "
                "opportunity across every league here.",
                kind="no-data",
            )
        )
        return actions

    account_profile = st.session_state.get("account_profile")
    sleeper_username = _safe_text(
        (account_profile or {}).get("sleeper_username") if isinstance(account_profile, Mapping) else ""
    )

    leagues: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    # Fan the per-league work (stance + GM targets + build_league_summary,
    # each its own Supabase/Sleeper round trip) out across a thread pool
    # instead of paying each saved league's latency back to back — see
    # _build_portfolio_row's docstring for why a plain-dict session
    # snapshot (never the live st.session_state) is what each worker gets.
    # executor.map yields results in `saved_rows` order regardless of which
    # worker finishes first, so zipping it back against saved_rows below
    # reproduces exactly the old sequential loop's ordering and output.
    session_snapshot = dict(st.session_state)
    worker = functools.partial(_build_portfolio_row, session_snapshot, sleeper_username, entitlement)
    max_workers = min(len(saved_rows), PORTFOLIO_FANOUT_MAX_WORKERS)
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix="dgm-portfolio-fanout"
    ) as executor:
        results = list(executor.map(worker, saved_rows))

    for row, result in zip(saved_rows, results):
        status = result["status"]
        if status == "skip":
            continue
        if status == "failed":
            failed.append(
                {
                    "league_id": result["league_id"],
                    "league_name": result["league_name"],
                    "reason": result["reason"],
                }
            )
            continue
        leagues.append(
            {
                **row,
                "league_id": result["league_id"],
                "league_name": result["league_name"],
                "summary": result["summary"],
            }
        )

    if failed:
        names = ", ".join(entry["league_name"] for entry in failed)
        plural = "league" if len(failed) == 1 else "leagues"
        render_html_fragment(
            status_badge_html(
                f"Couldn't load {len(failed)} {plural} right now: {names}. "
                "Everything else below is up to date.",
                variant="caution",
            )
        )

    if not leagues:
        render_html_fragment(
            empty_state_panel_html(
                "Portfolio is temporarily unavailable",
                "None of your saved leagues could be loaded right now. Try again in a moment.",
                kind="unavailable",
            )
        )
        return actions

    for entry in leagues:
        summary = entry["summary"]
        top_item = summary.get("top_item") or {}
        headline = _safe_text(top_item.get("headline"), "Open this league to see your Next Move.")
        reason = _safe_text(top_item.get("reason"))
        team_name = _safe_text(summary.get("team_name"), "Unclaimed team")
        metadata_bits = [
            bit
            for bit in (
                _record_label(summary),
                _rank_label(summary),
                summary.get("health_flag") if summary.get("health_flag") not in (None, "Stable") else "",
            )
            if bit
        ]
        render_html_fragment(
            content_card_html(
                reason or headline,
                title=f"{team_name} — {entry['league_name']}",
                metadata=" · ".join(metadata_bits),
                footer=headline if reason else "",
            )
        )
        if st.button(
            f"Open {entry['league_name']} Dashboard",
            key=f"portfolio_open_{entry['league_id']}",
            use_container_width=True,
        ):
            actions["open_league"] = dict(entry)

    return actions
