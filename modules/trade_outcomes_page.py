"""Web Trade History page — the quiet "did this trade actually work out?"
follow-up, already fully built on mobile and the backend; this module is
the web-side exposure, not a new feature.

Backend/mobile already own everything real here:
  - modules.push_triggers / services/mobile_api_service.py's
    POST /v1/leagues/{id}/trade-outcomes and the pending-answer endpoints
    record a shared trade and ask "did this happen?" (yes/no/didn't send).
  - modules.trade_outcome_results's standalone cron sweep computes, once a
    confirmed ('yes') trade has had RESULT_DELAY_DAYS to play out, a real
    before/after read from actual PPR production and value-score trend —
    never a guess, and only ever "insufficient_data" when there isn't
    enough real signal yet (see that module's own docstring for the full
    honesty contract this follows, same ethos as modules.player_projections
    and modules.college_scouting).
  - mobile/src/screens/TradeHistoryScreen.tsx is the existing pull-based
    (never pushed, never a popup) home for all of this on mobile.

This module reads the exact same `trade_outcomes` Supabase table directly
(the same way modules.account_store-backed pages like Portfolio and GM
Targets already read their own tables from web, rather than hopping
through services/mobile_api_service.py's HTTP layer), and renders it with
the same shared ui_primitives cards/badges the rest of web already uses —
no new visual language, no new valuation math, and no change to how trades
are proposed or accepted anywhere in the app. Purely additive exposure.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

import streamlit as st

from modules import account_store, auth_supabase
from modules.html_rendering import render_html_fragment
from modules.trade_outcome_results import VERDICT_LABELS
from modules.ui_primitives import content_card_html, empty_state_panel_html, status_badge_html

PAGE_KEY = "trade_history"
NAV_LABEL = "Trade History"
TRADE_OUTCOMES_TABLE = "trade_outcomes"

# Same table, same filter/select/order/limit shape as
# services/mobile_api_service.py's GET /v1/trade-outcomes/history — web and
# mobile read identical history for the same signed-in user.
HISTORY_QUERY = (
    "outcome=neq.pending"
    "&select=id,league_id,partner_team_name,trade_summary,outcome,shared_at,"
    "outcome_recorded_at,result_summary,result_computed_at"
    "&order=shared_at.desc&limit=50"
)

OUTCOME_LABELS = {"yes": "Made it", "no": "Didn't make it", "didnt_send": "Didn't send"}
OUTCOME_BADGE_VARIANT = {"yes": "success", "no": "neutral", "didnt_send": "neutral"}
VERDICT_BADGE_VARIANT = {
    "worked_out": "success",
    "didnt_pan_out": "danger",
    "mixed": "premium",
    "neutral": "neutral",
}

QUIET_EXPLAINER = (
    "Trades you've confirmed you made. Once a confirmed trade has had a few weeks "
    "to play out, we'll show a real before/after read here, using actual points "
    "scored and value trend, never a guess. Nothing here changes how trades are "
    "proposed or accepted."
)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _format_date(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return ""
    return parsed.strftime("%b %d, %Y")


def _asset_label(asset: Mapping[str, Any]) -> str:
    name = _safe_text(asset.get("name"))
    if not name:
        return ""
    position = _safe_text(asset.get("position"))
    return f"{name} ({position})" if position else name


def _asset_list_text(assets: Any) -> str:
    if not isinstance(assets, list):
        return "Nothing"
    labels = [_asset_label(asset) for asset in assets if isinstance(asset, Mapping)]
    labels = [label for label in labels if label]
    return ", ".join(labels) if labels else "Nothing"


def _verdict_detail_text(result: Mapping[str, Any]) -> str:
    """Mirrors mobile/src/screens/TradeHistoryScreen.tsx's verdictDetailText
    exactly — same two signals, same rounding, same separator."""

    parts: list[str] = []
    production = result.get("production")
    if isinstance(production, Mapping):
        try:
            avg = float(production.get("avg_net_per_week"))
        except (TypeError, ValueError):
            avg = None
        if avg is not None:
            sign = "+" if avg > 0 else ""
            parts.append(f"{sign}{avg:.1f} PPR pts/wk edge since the trade")
    value = result.get("value")
    if isinstance(value, Mapping):
        try:
            net = float(value.get("net_delta_pct"))
        except (TypeError, ValueError):
            net = None
        if net is not None:
            sign = "+" if net > 0 else ""
            parts.append(f"{sign}{net:.0f}% value trend edge")
    return " · ".join(parts)


def _render_trade_history_row(row: Mapping[str, Any]) -> None:
    summary = row.get("trade_summary") if isinstance(row.get("trade_summary"), Mapping) else {}
    partner = (
        _safe_text(row.get("partner_team_name"))
        or _safe_text(summary.get("partner_team_name"))
        or "your trade partner"
    )
    date = _format_date(row.get("shared_at"))
    title = f"{partner} · {date}" if date else partner

    outcome = _safe_text(row.get("outcome")).casefold()
    outcome_label = OUTCOME_LABELS.get(outcome, outcome.title() or "Unknown")
    badges_html = status_badge_html(outcome_label, variant=OUTCOME_BADGE_VARIANT.get(outcome, "neutral"))

    # Only a confirmed ('yes') trade can ever carry a real computed result —
    # same gate services/mobile_api_service.py's _project_trade_outcome_history
    # and the mobile screen both apply. A "ready" status is the only one with
    # an actual verdict; "insufficient_data" (or no result yet) shows no
    # verdict badge/body at all, never a fake "checking..." placeholder.
    body = ""
    if outcome == "yes":
        result = row.get("result_summary")
        if isinstance(result, Mapping) and result.get("status") == "ready":
            verdict = _safe_text(result.get("verdict"))
            verdict_label = _safe_text(result.get("verdict_label")) or VERDICT_LABELS.get(verdict, "")
            if verdict_label:
                badges_html += " " + status_badge_html(
                    verdict_label, variant=VERDICT_BADGE_VARIANT.get(verdict, "neutral")
                )
            body = _verdict_detail_text(result)

    render_html_fragment(badges_html)

    sent_text = _asset_list_text(summary.get("send"))
    received_text = _asset_list_text(summary.get("receive"))
    render_html_fragment(
        content_card_html(
            body,
            title=title,
            metadata=f"You sent: {sent_text} · You received: {received_text}",
        )
    )


def render_trade_history_page() -> None:
    """Render the Trade History page. Free feature (no Premium gate here —
    mirrors the mobile screen and mobile_api_service endpoints, neither of
    which gate on entitlement), requires only a signed-in account since
    `trade_outcomes` rows are keyed to `user_id`.
    """

    config = auth_supabase.get_supabase_config()
    user_id = auth_supabase.current_user_id(st.session_state)
    access_token = auth_supabase.current_access_token(st.session_state)
    if not user_id or not access_token:
        render_html_fragment(
            empty_state_panel_html(
                "Sign in to see your Trade History",
                "Trade History tracks trades you've confirmed you made, so it needs a signed-in account.",
                kind="unavailable",
            )
        )
        return

    rows, error = account_store.fetch_rows(
        config,
        access_token,
        TRADE_OUTCOMES_TABLE,
        user_id=user_id,
        extra_query=HISTORY_QUERY,
        timing_label="supabase_trade_outcomes_lookup",
    )
    if error:
        render_html_fragment(
            empty_state_panel_html(
                "Trade History is temporarily unavailable",
                account_store.customer_safe_error(error, context="trade_outcomes"),
                kind="unavailable",
            )
        )
        return

    if not rows:
        render_html_fragment(
            empty_state_panel_html(
                "No trade history yet",
                "Answer \"Did this trade happen?\" the next time it comes up, and it'll show up "
                "here — along with how it worked out, once there's enough real data.",
                kind="no-data",
            )
        )
        return

    st.caption(QUIET_EXPLAINER)

    for row in rows:
        if isinstance(row, Mapping):
            _render_trade_history_row(row)
