"""Alerts / Activity timeline presentation."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, MutableMapping, Sequence
from urllib.parse import urlparse
import re
import time

import streamlit as st

from modules import alerts_activity
from modules import player_images
from modules import player_profile_ui
from modules.alerts_activity_styles import ALERTS_ACTIVITY_CSS
from modules.html_rendering import inject_global_styles, render_html_fragment


def widget_safe_key(value: object) -> str:
    """Streamlit widget keys cannot rely on colons or spaces from event ids."""

    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    return (cleaned[:80].strip("_") or "none")


def _render_founder_action_diagnostics(stats: Mapping[str, Any]) -> None:
    try:
        from modules import founder_ops

        if not founder_ops.founder_ops_enabled():
            return
    except Exception:
        return
    parts = [
        f"{key}={int(stats.get(key) or 0)}"
        for key in (
            "visible_row_count",
            "unread_row_count",
            "dismissed_row_count",
            "rows_with_event_id",
            "mark_read_button_eligible_count",
            "dismiss_button_eligible_count",
            "rows_with_player_button",
            "duplicate_event_id_count",
            "pre_dedupe_event_count",
            "post_dedupe_event_count",
            "duplicate_article_count",
            "duplicate_identity_alias_count",
            "unread_count",
            "toast_candidates",
        )
    ]
    extra = [
        f"surface_seen={1 if stats.get('surface_seen') else 0}",
        f"actions_armed={1 if stats.get('actions_armed') else 0}",
        f"mass_replay={1 if stats.get('mass_action_replay_ignored') else 0}",
        f"explicit_read={int(stats.get('explicit_read_state_count') or 0)}",
        f"computed_unread={int(stats.get('computed_unread_count') or 0)}",
        f"dedupe_ms={stats.get('dedupe_ms') or 0}",
    ]
    st.caption("Founder alerts actions: " + " · ".join(parts + extra))


def filter_widget_key(league_id: str = "") -> str:
    scope = str(league_id or "none").strip() or "none"
    return f"alerts_filter_{scope}"


def alerts_page_header_html() -> str:
    """Masthead retired — page subtitle lives on the section header only."""

    return ""


def _safe_source_url(value: object) -> str:
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    return candidate if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else ""


# Presentation-only type taxonomy — mirrors the mobile Alerts screen's
# injury/status, transaction, role/depth, off-field buckets so alert TYPE
# reads via a per-row color accent (border/glyph). Reads only the
# already-computed `event_type` field; does not alter alert generation,
# matching, or eligibility logic. Section GROUPING is decision-tier based
# (see `alert_priority_tier` below), not type-based — see V2 restructure notes.
_BUCKET_INJURY_EVENTS = frozenset(
    {
        "INJURY",
        "INACTIVE",
        "IR_PUP_NFI",
        "INJURY_SEVERITY_UPDATE",
        "RETURN_TO_PLAY",
        "RETURN_TO_PRACTICE",
        "ACTIVE",
    }
)
_BUCKET_TRANSACTION_EVENTS = frozenset(
    {"TRADE", "SIGNING", "RELEASE", "SUSPENSION", "RETIREMENT"}
)
_BUCKET_ROLE_EVENTS = frozenset(
    {
        "STARTER_CHANGE",
        "ROLE_INCREASE",
        "ROLE_DECREASE",
        "POSITION_BATTLE",
        "DEPTH_CHART_CHANGE",
    }
)


def alert_category_bucket(row: Mapping[str, Any]) -> str:
    """Presentation-only bucket for a row's type-color accent; not a business signal."""

    event_type = str(row.get("event_type") or "").strip().upper()
    if event_type in _BUCKET_INJURY_EVENTS:
        return "injury"
    if event_type in _BUCKET_TRANSACTION_EVENTS:
        return "transaction"
    if event_type in _BUCKET_ROLE_EVENTS:
        return "role"
    return "other"


# V2 restructure: sections are grouped by user decision-importance (urgency +
# roster stakes), not by backend event-type taxonomy. `compose_activity_timeline`
# already orders rows "mine" before "rest"; this tier split rides that existing
# order (no new sort, no change to ranking/relevance logic) so groups never
# interleave the way the old per-event-type buckets could when an injury row
# and a transaction row about the same roster alternated in ranked order.
_TIER_ATTENTION = "attention"
_TIER_MY_PLAYERS = "my_players"
_TIER_LEAGUE = "league"

_ALERT_TIER_LABELS = {
    _TIER_ATTENTION: "Needs Your Attention",
    _TIER_MY_PLAYERS: "My Players",
    _TIER_LEAGUE: "Around the League",
}

# Roster-relationship labels — shared by the priority-tier badge and the
# unconfirmed-status context line so both surfaces agree on wording.
_ROSTER_RELATIONSHIP_LABELS = {
    "MY_STARTER": "Starter",
    "MY_BENCH": "Bench",
    "MY_TAXI": "Taxi squad",
    "MY_IR": "IR",
}

# Injury/status event types where an unconfirmed report already gets a
# dedicated, cautious context line (see `timeline_row_html`) instead of
# parroting a possibly-premature reason. Kept as one constant so the
# generalized "Unconfirmed" badge below never duplicates that treatment.
_INJURY_STATUS_EVENT_TYPES = frozenset(
    {"INJURY", "INACTIVE", "IR_PUP_NFI", "INJURY_SEVERITY_UPDATE"}
)


def _row_relationship_flags(row: Mapping[str, Any]) -> tuple[bool, bool, bool, str]:
    """Return (is_my_player, is_teammate, is_urgent, relationship) for one row.

    Single source of truth for both row styling (`timeline_row_html`) and
    section grouping (`alert_priority_tier`) so the two can never disagree
    about which tier/accent a row belongs to.
    """

    relationship = str(row.get("roster_relationship") or "").strip().upper()
    severity = str(row.get("severity") or "").strip().upper()
    is_my_player = relationship in alerts_activity._MY_REL
    is_teammate = str(row.get("relationship_kind") or "") == alerts_activity.KIND_MY_TEAMMATE
    if is_teammate:
        is_my_player = False
    is_urgent = severity in {"CRITICAL", "HIGH"} and relationship in alerts_activity._MY_REL
    return is_my_player, is_teammate, is_urgent, relationship


def alert_priority_tier(row: Mapping[str, Any]) -> str:
    """Decision-importance tier used for section grouping (presentation only).

    Urgent roster-relevant alerts lead, then other My Players activity, then
    everything else — answering "what do I need to act on?" before "what
    happened around the league?" per the app's information-hierarchy rule.
    """

    is_my_player, is_teammate, is_urgent, _relationship = _row_relationship_flags(row)
    if is_urgent:
        return _TIER_ATTENTION
    if is_my_player or is_teammate:
        return _TIER_MY_PLAYERS
    return _TIER_LEAGUE


def timeline_row_html(row: Mapping[str, Any]) -> str:
    glyph = escape(str(row.get("glyph") or "NEWS")[:10])
    headline = escape(alerts_activity.humanize_headline(row))
    context = escape(str(row.get("context") or ""))
    freshness = escape(str(row.get("freshness") or ""))
    unread = bool(row.get("unread"))
    severity = str(row.get("severity") or "").strip().upper()
    event_type = str(row.get("event_type") or "").strip().upper()
    is_my_player, is_teammate, is_urgent, relationship = _row_relationship_flags(row)
    bucket = alert_category_bucket(row)
    row_classes = ["dg-alerts-row"]
    player_id = str(row.get("player_id") or "").strip()
    if player_id:
        row_classes.append("dg-alerts-row--player")
    if bucket == "injury":
        row_classes.append("dg-alerts-row--injury")
    elif bucket == "transaction":
        row_classes.append("dg-alerts-row--transaction")
    elif bucket == "role":
        row_classes.append("dg-alerts-row--role")
    if is_urgent:
        row_classes.extend(("dg-alerts-row--urgent", "dg-alerts-row--my-player"))
    elif is_teammate:
        row_classes.append("dg-alerts-row--teammate")
    elif str(row.get("category") or "").upper() == "NEWS":
        row_classes.append("dg-alerts-row--news")
    if not unread:
        row_classes.append("dg-alerts-row--read")
    status_unconfirmed = bool(row.get("status_unconfirmed"))
    # An unconfirmed injury/status report on a My Player row gets its own
    # cautious context line below (real reason text intentionally withheld —
    # see that branch) instead of this generic badge, so the two treatments
    # never both fire on the same row.
    unconfirmed_has_dedicated_context = (
        is_my_player and event_type in _INJURY_STATUS_EVENT_TYPES and status_unconfirmed
    )
    badges: list[str] = []
    if is_my_player:
        relationship_suffix = _ROSTER_RELATIONSHIP_LABELS.get(relationship, "")
        my_player_label = (
            f"MY PLAYER · {relationship_suffix.upper()}" if relationship_suffix else "MY PLAYER"
        )
        badges.append(f"<span class='dg-alerts-badge dg-alerts-badge--my'>{my_player_label}</span>")
    elif is_teammate:
        badges.append("<span class='dg-alerts-badge dg-alerts-badge--my'>TEAMMATE CONTEXT</span>")
    if event_type in _INJURY_STATUS_EVENT_TYPES:
        event_label = (
            "POTENTIALLY SIGNIFICANT INJURY"
            if bool(row.get("significant_injury_event"))
            else "INJURY ALERT"
        )
        badges.append(f"<span class='dg-alerts-badge dg-alerts-badge--risk'>{event_label}</span>")
    if status_unconfirmed and not unconfirmed_has_dedicated_context:
        # Unconfirmed/speculative info must never read with the same
        # confidence as a confirmed report — mirrors the fix already shipped
        # on mobile (PR #761): give it its own distinct, amber "pending"
        # treatment instead of blending it into ordinary metadata text.
        badges.append("<span class='dg-alerts-badge dg-alerts-badge--pending'>UNCONFIRMED</span>")
    badges_html = (
        "<div class='dg-alerts-badges'>" + "".join(badges) + "</div>"
        if badges
        else ""
    )
    unread_html = "<span class='dg-alerts-unread' aria-label='Unread'></span>" if unread else ""
    context = str(row.get("fantasygm_read") or row.get("context") or "")
    context_pending = False
    if unconfirmed_has_dedicated_context:
        relationship_label = _ROSTER_RELATIONSHIP_LABELS.get(relationship, "My roster")
        context = " · ".join(
            part for part in (relationship_label, "Status not yet confirmed") if part
        )
        context_pending = True
    context = escape(context)
    context_classes = "dg-alerts-context" + (" dg-alerts-context--pending" if context_pending else "")
    context_html = f"<p class='{context_classes}'>{context}</p>" if context else ""
    event_label = event_type.replace("_", " ").title() if event_type else str(row.get("category") or "")
    source_name = str(row.get("source") or "").strip()
    meta_parts = [part for part in (event_label, source_name, freshness) if part]
    meta = escape(" · ".join(meta_parts))
    source_url = _safe_source_url(row.get("source_url"))
    headline_html = f"<p class='dg-alerts-headline'>{headline}</p>"
    source_link_html = (
        f"<a class='dg-alerts-source' href='{escape(source_url, quote=True)}' "
        f"target='_blank' rel='noopener noreferrer' "
        f"data-dg-alerts-source='1'>Read source</a>"
        if source_url
        else ""
    )
    player_name = str(row.get("player_name") or headline or "Player").strip()
    initials = "".join(part[:1] for part in player_name.split()[:2]).upper() or "?"
    visual_html = f"<div class='dg-alerts-glyph'>{glyph}</div>"
    if player_id:
        portrait = player_profile_ui.avatar_html(
            player_images.get_player_image_url(player_id),
            initials,
            css_class="dg-alerts-portrait",
        )
        visual_html = portrait
    article_open = f"<article class='{' '.join(row_classes)}'"
    article_open += " aria-label='URGENT player alert'>" if is_urgent else ">"
    return (
        article_open
        + visual_html
        + "<div>"
        f"{headline_html}"
        f"{badges_html}"
        f"{context_html}"
        f"<div class='dg-alerts-meta'>{unread_html}<span>{meta}</span>{source_link_html}</div>"
        "</div>"
        "</article>"
    )


def render_alerts_page(
    *,
    league_id: str = "",
    session: Mapping[str, Any] | None = None,
    entitlement: str = "free",
    render_section_header=None,
    open_player_quick_view=None,
    fresh_entry: bool = False,
    players_df=None,
    my_roster_ids: Sequence[Any] | None = None,
    roster_id: str = "",
    taxi_ids: Sequence[Any] | None = None,
    ir_ids: Sequence[Any] | None = None,
    opponent_ids: Sequence[Any] | None = None,
    roster_player_map: Mapping[Any, Any] | None = None,
) -> None:
    inject_global_styles(ALERTS_ACTIVITY_CSS)
    if render_section_header is not None:
        render_section_header(
            "Alerts",
            kicker="Activity",
            note="Priority signals in one timeline.",
        )
    target = session if isinstance(session, MutableMapping) else st.session_state
    hydrate_stats = alerts_activity.hydrate_alerts_first_paint(
        target if isinstance(target, MutableMapping) else None,
        league_id=league_id,
        roster_id=roster_id,
        my_roster_ids=my_roster_ids,
        taxi_ids=taxi_ids,
        ir_ids=ir_ids,
        opponent_ids=opponent_ids,
        players_df=players_df,
        roster_player_map=roster_player_map,
    )
    applied_action_keys = set()
    if isinstance(target, MutableMapping):
        applied_action_keys.update(
            alerts_activity.consume_pending_alert_actions(
                target,
                league_id=league_id,
                open_player_quick_view=open_player_quick_view,
            )
        )
    rows = alerts_activity.compose_activity_timeline(
        session=target,
        league_id=league_id,
        entitlement=entitlement,
    )
    render_started = time.perf_counter()
    refresh_scheduled = False
    try:
        from modules.news import schedule_news_cache_refresh

        refresh_scheduled = bool(schedule_news_cache_refresh())
    except Exception:
        refresh_scheduled = False
    key = filter_widget_key(league_id)
    control_key = f"{key}_control"
    owner_key = f"{key}_selected"
    if fresh_entry or owner_key not in st.session_state:
        st.session_state[owner_key] = alerts_activity.FILTER_MY_PLAYERS
    if control_key not in st.session_state:
        st.session_state[control_key] = st.session_state[owner_key]
    stored_filter = st.session_state.get(owner_key, st.session_state.get(control_key))
    default = alerts_activity.normalize_filter(
        stored_filter,
        default=alerts_activity.FILTER_MY_PLAYERS,
    )
    if stored_filter == "Important":
        st.session_state[control_key] = default
        st.session_state[owner_key] = default
    with st.container(key=key):
        selected = st.pills(
            "Timeline filter",
            list(alerts_activity.ALERT_FILTERS),
            key=control_key,
            label_visibility="collapsed",
        )
    if selected:
        st.session_state[owner_key] = alerts_activity.normalize_filter(
            selected, default=default
        )
    selected_label = alerts_activity.normalize_filter(
        st.session_state.get(owner_key) or selected or default,
        default=alerts_activity.FILTER_MY_PLAYERS,
    )
    from modules import news_intelligence as _ni

    roster_context = _ni.load_news_roster_context(
        session if session is not None else st.session_state,
        league_id=league_id,
    )
    visible = alerts_activity.filter_timeline(
        rows,
        selected_label,
        my_roster_ids=roster_context.get("my_roster_ids") or (),
        session=target,
        league_id=league_id,
    )
    dismissed = 0
    unread = 0
    inbox_count = 0
    activity_inventory_count = 0
    if isinstance(target, Mapping):
        from modules import notification_center as _nc

        inbox = _nc.compose_activity_inbox(
            session=target, league_id=league_id, header_cap=False
        )
        inbox_count = len(inbox)
        unread = _nc.unread_count(inbox)
        dismissed = sum(
            1
            for item in inbox
            if _nc.is_notification_dismissed(target, item.id, league_id=league_id)
        )
        snapshot = target.get(_nc.ACTIVITY_INBOX_SNAPSHOT_KEY)
        activity_inventory_count = (
            len(snapshot.get("records") or ())
            if isinstance(snapshot, Mapping)
            else 0
        )
    seen_scope = f"{alerts_activity.SURFACE_SEEN_KEY}:{str(league_id or '').strip()}"
    if isinstance(target, MutableMapping):
        target[seen_scope] = True
    hydrate_payload = dict(hydrate_stats)
    hydrate_payload.pop("rerun_requested", None)
    alerts_activity.record_pipeline_stats(
        target,
        **hydrate_payload,
        my_players_visible_count=len(visible)
        if selected_label == alerts_activity.FILTER_MY_PLAYERS
        else sum(
            1
            for row in visible
            if alerts_activity._row_is_roster_relevant(
                row, roster_context.get("my_roster_ids") or ()
            )
        ),
        generic_visible_count=sum(
            1
            for row in visible
            if not alerts_activity._row_is_roster_relevant(
                row, roster_context.get("my_roster_ids") or ()
            )
        ),
        unread_count=unread,
        dismissed_count=dismissed,
        inbox_count=inbox_count,
        activity_inventory_count=activity_inventory_count,
        background_refresh_scheduled=refresh_scheduled,
        rerun_requested=False,
        render_ms=round((time.perf_counter() - render_started) * 1000, 2),
    )
    action_stats = alerts_activity.action_rail_diagnostics(
        visible,
        player_button_available=open_player_quick_view is not None,
    )
    alerts_activity.record_pipeline_stats(target, **action_stats)
    if not visible:
        copy = escape(alerts_activity.empty_copy(selected_label))
        render_html_fragment(f"<p class='dg-alerts-empty'>{copy}</p>")
        alerts_activity.remember_alert_row_actions(
            target if isinstance(target, MutableMapping) else None, ()
        )
        derivation = alerts_activity.unread_derivation_diagnostics(
            visible, session=target, league_id=league_id
        )
        alerts_activity.record_pipeline_stats(target, **derivation)
        _render_founder_action_diagnostics({**action_stats, **derivation})
        alerts_activity.arm_alert_row_actions(target)
        return
    clicked_actions: list[dict[str, Any]] = []
    painted_actions: list[dict[str, Any]] = []
    current_tier = None
    with st.container(key=f"{key}_timeline"):
        for index, row in enumerate(visible):
            tier = alert_priority_tier(row)
            if tier != current_tier:
                current_tier = tier
                tier_css = tier.replace("_", "-")
                render_html_fragment(
                    f"<div class='dg-alerts-group dg-alerts-group--{tier_css}'>"
                    "<span class='dg-alerts-group__bar'></span>"
                    f"{escape(_ALERT_TIER_LABELS[tier])}</div>"
                )
            with st.container(key=f"alerts_item_{league_id}_{index}"):
                render_html_fragment(timeline_row_html(row))
                attention_id = str(
                    row.get("attention_id")
                    or row.get("event_identity")
                    or row.get("id")
                    or row.get("recommendation_id")
                    or f"row-{index}"
                ).strip()
                event_id = attention_id
                unread_row = bool(row.get("unread"))
                dismissed_row = bool(row.get("dismissed"))
                player_id = str(
                    row.get("beneficiary_player_id") or row.get("player_id") or ""
                ).strip()
                mine = {
                    str(pid).strip()
                    for pid in (roster_context.get("my_roster_ids") or ())
                    if str(pid).strip()
                }
                if str(row.get("player_id") or "").strip() in mine:
                    player_id = str(row.get("player_id") or "").strip()
                safe = widget_safe_key(f"{league_id}_{index}_{attention_id}")
                actions: list[tuple[str, str, str]] = []
                if player_id and open_player_quick_view is not None:
                    actions.append(
                        (
                            "Open player",
                            f"alerts_action_player_{safe}_{widget_safe_key(player_id)}",
                            "open_player",
                        )
                    )
                if unread_row:
                    actions.append(("Mark read", f"alerts_action_read_{safe}", "mark_read"))
                if not dismissed_row:
                    actions.append(("Dismiss", f"alerts_action_dismiss_{safe}", "dismiss"))
                if actions:
                    with st.container(key=f"alerts_actions_{safe}"):
                        columns = st.columns(len(actions), gap="small")
                        for column, (label, action_key, kind) in zip(columns, actions):
                            spec = {
                                "kind": kind,
                                "key": action_key,
                                "row": dict(row),
                                "player_id": player_id,
                                "event_id": event_id,
                            }
                            painted_actions.append(spec)
                            with column:
                                pressed = st.button(
                                    label,
                                    key=action_key,
                                    type="tertiary",
                                    use_container_width=False,
                                )
                                if pressed:
                                    clicked_actions.append(spec)
    accepted = alerts_activity.select_explicit_alert_actions(clicked_actions, target)
    leftover = [
        action
        for action in accepted
        if str(action.get("key") or "") not in applied_action_keys
    ]
    alerts_activity.apply_explicit_alert_actions(
        leftover,
        target if isinstance(target, MutableMapping) else None,
        league_id=league_id,
        open_player_quick_view=open_player_quick_view,
    )
    alerts_activity.remember_alert_row_actions(
        target if isinstance(target, MutableMapping) else None,
        painted_actions,
    )
    derivation = alerts_activity.unread_derivation_diagnostics(
        visible, session=target, league_id=league_id
    )
    alerts_activity.record_pipeline_stats(target, **derivation)
    _render_founder_action_diagnostics({**action_stats, **derivation})
    alerts_activity.arm_alert_row_actions(target)
