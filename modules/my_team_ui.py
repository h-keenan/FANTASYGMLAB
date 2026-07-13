from html import escape
from typing import Callable

import pandas as pd
import streamlit as st


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def _safe_positive_int(value, default: int = 0) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def render_roster_limit_alert(
    limit_context: dict,
    *,
    compact: bool = False,
    render_summary_tiles: Callable,
    render_visible_decision_source_debug: Callable,
    render_no_team_player_debug: Callable,
    render_recommendation_feedback: Callable,
    render_structured_decision_cards: Callable,
    render_roster_utility_debug: Callable,
) -> None:
    if not limit_context.get("over_limit"):
        return

    over_by = _safe_positive_int(limit_context.get("over_by"), 0)
    current_size = _safe_positive_int(limit_context.get("current_roster_size"), 0)
    max_size = _safe_positive_int(limit_context.get("max_roster_size"), 0)
    total_size = _safe_positive_int(limit_context.get("total_rostered_players"), current_size)
    taxi_count = _safe_positive_int(limit_context.get("taxi_count"), 0)
    reserve_count = _safe_positive_int(limit_context.get("reserve_count"), 0)
    exempt_count = _safe_positive_int(limit_context.get("exempt_player_count"), 0)
    strongest_surplus = ", ".join(limit_context.get("strongest_surplus_positions") or []) or "None"
    thinnest_positions = ", ".join(limit_context.get("thinnest_positions") or []) or "None"
    replaceable_lineup_needs = ", ".join(
        limit_context.get("replaceable_lineup_needs") or []
    )
    thin_notes = limit_context.get("thinnest_position_notes") or {}
    thin_note = " | ".join(
        _safe_text(thin_notes.get(position))
        for position in (limit_context.get("thinnest_positions") or [])[:2]
        if _safe_text(thin_notes.get(position))
    )
    exempt_parts = []
    if taxi_count > 0:
        exempt_parts.append(f"{taxi_count} taxi")
    if reserve_count > 0:
        exempt_parts.append(f"{reserve_count} IR")
    exempt_note = " | ".join(exempt_parts)
    st.markdown(
        "<div class='dg-alert-banner dg-alert-warning'>"
        + "<div class='dg-alert-kicker'><span class='dg-semantic-icon' aria-hidden='true'>!</span>Roster Pressure</div>"
        + f"<div class='dg-alert-title'>{current_size}/{max_size} active rostered</div>"
        + "<div class='dg-alert-body'>"
        + f"Sleeper is counting {current_size} players against the active roster. You need to clear {over_by} slot"
        + ("s." if over_by != 1 else ".")
        + "</div></div>",
        unsafe_allow_html=True,
    )
    roster_note = (
        f"{total_size} total rostered"
        + (f" | {exempt_count} exempt via {exempt_note}" if exempt_count > 0 and exempt_note else "")
    )
    thin_copy = (
        (
            thin_note + ". "
            if thin_note
            else ""
        )
        + "Protect thin long-term rooms."
        + (
            f" Temporary lineup need: {replaceable_lineup_needs}."
            if replaceable_lineup_needs
            else ""
        )
    )
    st.markdown(
        "<div class='roster-limit-strip'>"
        + "<div class='roster-limit-stat roster-limit-stat-danger'>"
        + "<span><span class='dg-semantic-icon' aria-hidden='true'>!</span>Active</span>"
        + f"<strong>{current_size}/{max_size}</strong>"
        + f"<small>{escape(roster_note)}</small>"
        + "</div>"
        + "<div class='roster-limit-stat roster-limit-stat-danger'>"
        + "<span><span class='dg-semantic-icon' aria-hidden='true'>!</span>Over</span>"
        + f"<strong>{over_by}</strong>"
        + "<small>Slots to clear</small>"
        + "</div>"
        + "<div class='roster-limit-stat'>"
        + "<span><span class='dg-semantic-icon' aria-hidden='true'>+</span>Surplus</span>"
        + f"<strong>{escape(strongest_surplus)}</strong>"
        + "<small>Best rooms to shop</small>"
        + "</div>"
        + "<div class='roster-limit-stat roster-limit-stat-warning'>"
        + "<span><span class='dg-semantic-icon' aria-hidden='true'>*</span>Protect</span>"
        + f"<strong>{escape(thinnest_positions)}</strong>"
        + f"<small>{escape(thin_copy)}</small>"
        + "</div>"
        + "<div class='roster-limit-stat'>"
        + "<span><span class='dg-semantic-icon' aria-hidden='true'>+</span>Taxi / IR</span>"
        + f"<strong>{_safe_positive_int(limit_context.get('open_taxi_slots'), 0)} / {_safe_positive_int(limit_context.get('open_ir_slots'), 0)}</strong>"
        + "<small>Use exempt slots first</small>"
        + "</div>"
        + "</div>",
        unsafe_allow_html=True,
    )
    cards = [
        {
            "label": "Move Now",
            "title": "Use exempt slots first",
            "candidates": list(limit_context.get("move_candidates_structured") or []),
            "empty_note": "No clean taxi or IR move is available right now.",
            "tone": "opportunity",
        },
        {
            "label": "Better Trade-Away Than Drop",
            "title": "Preserve value where you still can",
            "candidates": list(limit_context.get("trade_candidates_structured") or []),
            "empty_note": "No obvious trade-out candidate stands above the rest.",
            "tone": "strength",
        },
        {
            "label": "Best Drop Candidates",
            "title": "Lowest-utility cuts",
            "candidates": list(limit_context.get("drop_candidates_structured") or []),
            "empty_note": "No obvious cut stands out beyond current hold candidates.",
            "tone": "risk",
        },
    ]
    keep_candidates = list(limit_context.get("keep_candidates_structured") or [])
    if keep_candidates:
        cards.append(
            {
                "label": "Hold Despite Roster Pressure",
                "title": "Protected low-value holds",
                "candidates": keep_candidates,
                "empty_note": "No special stash hold is standing out right now.",
                "tone": "reference",
            }
        )
    render_visible_decision_source_debug(
        limit_context.get("drop_candidates_structured"),
        title="Decision Debug: Final Visible Drop Candidates",
    )
    render_no_team_player_debug(limit_context.get("rostered_no_team_players"))
    report_candidates = [
        item
        for card in cards
        for item in (card.get("candidates") or [])
        if isinstance(item, dict)
    ]

    def render_roster_limit_feedback() -> None:
        render_recommendation_feedback(
            page="my_team",
            surface="My Team - Roster Limit Alert",
            recommendation_type="roster_limit_decisions",
            key_prefix="my_team_roster_limit_feedback",
            recommendation_title=f"Clear {over_by} roster slot{'s' if over_by != 1 else ''}",
            recommendation_summary=f"{current_size}/{max_size} active rostered.",
            player_ids=[item.get("player_id") for item in report_candidates],
            player_names=[item.get("player_name") or item.get("name") for item in report_candidates],
            score_fields={
                "current_roster_size": current_size,
                "max_roster_size": max_size,
                "players_over": over_by,
            },
            reason_fields={
                "candidates": [
                    {
                        "player_id": item.get("player_id"),
                        "bucket": item.get("bucket"),
                        "reason": item.get("reason"),
                    }
                    for item in report_candidates
                ]
            },
        )

    if compact:
        render_structured_decision_cards(cards, container_class="decision-panel-grid-alert")
        render_roster_limit_feedback()
        render_roster_utility_debug(limit_context.get("lowest_utility_candidates"))
        return

    if not keep_candidates:
        cards.append(
            {
                "label": "Hold Despite Roster Pressure",
                "title": "Protected low-value holds",
                "candidates": [],
                "empty_note": "No special stash hold is standing out right now.",
                "tone": "reference",
            }
        )
    render_structured_decision_cards(cards, container_class="decision-panel-grid-alert")
    render_roster_limit_feedback()
    render_roster_utility_debug(limit_context.get("lowest_utility_candidates"))
    render_no_team_player_debug(limit_context.get("rostered_no_team_players"))


def render_advice_cards(advice_items: list[dict]) -> None:
    cards = []
    for item in advice_items:
        primary = " advice-card-primary" if item.get("primary") else ""
        tone = ""
        label = _safe_text(item.get("label")).strip().lower()
        if item.get("primary") or label == "priority":
            tone = " advice-card-priority"
        elif label in {"need", "age"}:
            tone = " advice-card-need"
        elif label == "health":
            tone = " advice-card-health"
        elif label in {"depth", "leverage", "window"}:
            tone = " advice-card-opportunity"
        cards.append(
            "<div class='advice-card"
            + primary
            + tone
            + "'>"
            + f"<div class='advice-label'>{escape(_safe_text(item.get('label')))}</div>"
            + f"<div class='advice-title'>{escape(_safe_text(item.get('title')))}</div>"
            + f"<div class='advice-body'>{escape(_safe_text(item.get('body')))}</div>"
            + "</div>"
        )
    st.markdown("<div class='advice-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_prospect_watchlist(
    needed_positions: list[str],
    *,
    prospects_for_positions: Callable,
) -> None:
    prospects = prospects_for_positions(needed_positions, limit=6)
    if not prospects:
        return
    grouped: dict[str, list[dict]] = {}
    for prospect in prospects:
        position = _safe_text(prospect.get("position"), "Best Fit").upper()
        grouped.setdefault(position, []).append(prospect)

    sections = []
    for position in needed_positions:
        position = _safe_text(position).upper()
        position_prospects = grouped.get(position, [])
        if not position_prospects:
            continue
        cards = []
        for prospect in position_prospects:
            label = f"{position} | {prospect.get('school', '')}"
            source = prospect.get("source", "")
            meta = f"2027 watchlist | {source}" if source else "2027 watchlist"
            cards.append(
                "<div class='prospect-card'>"
                + "<div class='prospect-card-head'>"
                + "<div class='prospect-card-title-group'>"
                + f"<div class='prospect-label'>{escape(label)}</div>"
                + f"<div class='prospect-name'>{escape(prospect.get('name', 'Prospect'))}</div>"
                + "</div>"
                + f"<div class='prospect-meta'>{escape(meta)}</div>"
                + "</div>"
                + f"<div class='prospect-note'>{escape(prospect.get('note', 'Monitor draft value.'))}</div>"
                + "</div>"
            )
        sections.append(
            "<section class='prospect-position-group'>"
            + f"<div class='prospect-position-title'>{escape(position)} watch</div>"
            + "<div class='prospect-grid'>"
            + "".join(cards)
            + "</div></section>"
        )
    st.markdown("<div class='prospect-watch-groups'>" + "".join(sections) + "</div>", unsafe_allow_html=True)


def render_my_team_workspace(
    *,
    biggest_need_value: str,
    biggest_need_note: str,
    trade_target_value: str,
    trade_opportunity_note: str,
    trade_target_row,
    waiver_value: str,
    waiver_note: str,
    top_waiver,
    roster_limit_value: str,
    roster_limit_note: str,
    injury_alert_value: str,
    injury_alert_note: str,
    immediate_value: str,
    immediate_note: str,
    immediate_tone: str,
    my_roster_limit: dict,
    core_assets_df: pd.DataFrame,
    untouchables_df: pd.DataFrame,
    trade_candidates_df: pd.DataFrame,
    hold_candidates_df: pd.DataFrame,
    drop_candidates_df: pd.DataFrame,
    trade_note_map: dict,
    hold_note_map: dict,
    drop_note_map: dict,
    starters: pd.DataFrame,
    key_backups_df: pd.DataFrame,
    strengths: list,
    weaknesses: list,
    team_row,
    active_team_strategy_label: str,
    auto_team_strategy: str,
    health_flag: str,
    injured_starters: int,
    key_injuries_summary: str,
    league_rank_rows: pd.DataFrame | None = None,
    selected_league_id: str,
    my_roster_id,
    score_field: str,
    render_section_header: Callable,
    render_home_command_tiles: Callable,
    render_roster_limit_alert: Callable,
    render_player_scan_cards: Callable,
    render_roster_utility_debug: Callable,
    render_no_team_player_debug: Callable,
    render_summary_tiles: Callable,
    player_display_name: Callable,
    format_score: Callable,
    format_rank: Callable,
    truncate_text: Callable,
    team_strategy_label: Callable,
    is_premium: bool = True,
    render_premium_lock: Callable | None = None,
) -> None:
    league_rank_rows = league_rank_rows if league_rank_rows is not None else pd.DataFrame()

    def rank_detail_items(rank_column: str, score_column: str = "") -> list[dict]:
        if league_rank_rows is None or league_rank_rows.empty or rank_column not in league_rank_rows.columns:
            return []
        sort_frame = league_rank_rows.copy()
        sort_frame["_rank_sort"] = pd.to_numeric(sort_frame.get(rank_column), errors="coerce").fillna(999)
        sort_frame = sort_frame.sort_values(["_rank_sort", "team_name"], ascending=[True, True]).head(12)
        rows = []
        for _, rank_row in sort_frame.iterrows():
            rank_value = _safe_positive_int(rank_row.get(rank_column), 0)
            team_name = _safe_text(rank_row.get("team_name"), "Team")
            note_parts = []
            if score_column and score_column in rank_row.index:
                note_parts.append(f"Score {_safe_text(rank_row.get(score_column))}")
            if "strategy_label" in rank_row.index and _safe_text(rank_row.get("strategy_label")):
                note_parts.append(_safe_text(rank_row.get("strategy_label")))
            rows.append(
                {
                    "title": team_name,
                    "value": f"#{rank_value}" if rank_value else "N/A",
                    "note": " | ".join(note_parts),
                    "current": str(rank_row.get("roster_id")) == str(my_roster_id),
                }
            )
        return rows

    def room_detail_items(rooms: list, *, empty: str) -> list[dict]:
        clean_rooms = [_safe_text(room).upper() for room in rooms or [] if _safe_text(room)]
        if not clean_rooms:
            return [{"title": empty, "note": "No position room is separating strongly from the rest right now."}]
        return [{"title": room, "note": "Current roster room signal from existing team metrics."} for room in clean_rooms[:4]]

    def health_detail_items() -> list[dict]:
        if key_injuries_summary:
            return [{"title": part.strip(), "note": "Existing injury context"} for part in key_injuries_summary.split(";") if part.strip()]
        if injured_starters:
            return [{"title": f"{injured_starters} injured projected starter{'s' if injured_starters != 1 else ''}", "note": "Player-level detail is unavailable in this summary view."}]
        return [{"title": "No high-value injury concern", "note": "No injured starter cluster is driving this tile."}]

    def safe_list(value) -> list:
        return value if isinstance(value, list) else []

    render_section_header(
        "Roster Priorities",
        kicker="What to do next",
        note="Start here: team need, trade/waiver paths, roster limit, and injury pressure.",
    )
    render_home_command_tiles(
        [
            {
                "label": "Biggest Need",
                "value": biggest_need_value,
                "note": biggest_need_note,
                "tone": "need",
            },
            {
                "label": "Top Trade Opportunity",
                "value": trade_target_value,
                "note": trade_opportunity_note,
                "tone": "trade",
                "player_row": trade_target_row,
                "recommendation_label": "Trade Target",
                "score_field": score_field,
                "route_key": "trade_hub",
                "route_player_id": _safe_text(trade_target_row.get("player_id")) if trade_target_row is not None and hasattr(trade_target_row, "get") else "",
                "route_focus_mode": "target_player",
            },
            {
                "label": "Top Waiver Opportunity",
                "value": waiver_value,
                "note": waiver_note,
                "tone": "waiver",
                "player_row": top_waiver if top_waiver is not None and not top_waiver.empty else None,
                "recommendation_label": "Priority Add",
                "score_field": score_field,
            },
            *(
                []
                if my_roster_limit.get("over_limit")
                else [
                    {
                        "label": "Roster Status",
                        "value": roster_limit_value,
                        "note": roster_limit_note,
                        "tone": "risk",
                    }
                ]
            ),
            {
                "label": "Injury Alerts",
                "value": injury_alert_value,
                "note": injury_alert_note,
                "tone": "risk",
            },
            *(
                []
                if my_roster_limit.get("over_limit")
                else [
                    {
                        "label": "Next Move",
                        "value": immediate_value,
                        "note": immediate_note,
                        "tone": immediate_tone,
                        "wide": True,
                    }
                ]
            ),
        ]
    )
    if my_roster_limit.get("over_limit"):
        render_roster_limit_alert(my_roster_limit, compact=True)

    render_section_header(
        "Room Snapshot",
        kicker="Roster health",
        note="Strengths, weaknesses, starter quality, and injury trust before the player-by-player lists.",
    )
    render_summary_tiles(
        [
            {
                "label": "Starter Unit",
                "value": format_score(team_row.get("starter_score")),
                "note": f"Starter rank {format_rank(team_row.get('starter_rank'))} | {len(starters)} projected starters",
                "tone": "power",
                "detail_items_title": "Starter Context",
                "detail_items": [
                    {
                        "title": "Projected starters",
                        "value": str(len(starters)),
                        "note": f"Starter rank {format_rank(team_row.get('starter_rank'))}",
                    },
                    {
                        "title": "Starter score",
                        "value": format_score(team_row.get("starter_score")),
                        "note": "Current starter-unit score from existing team evaluation.",
                    },
                ],
            },
            {
                "label": "Weak Positions",
                "value": " / ".join(weaknesses[:2]) if weaknesses else "None",
                "note": "Rooms that should drive trade and waiver attention.",
                "tone": "weakness",
                "detail_items_title": "Pressure Rooms",
                "detail_items": room_detail_items(weaknesses, empty="No clear weak room"),
            },
            {
                "label": "Strength Positions",
                "value": " / ".join(strengths[:2]) if strengths else "Balanced",
                "note": "Best leverage for two-for-one or surplus-for-need moves.",
                "tone": "strength",
                "detail_items_title": "Leverage Rooms",
                "detail_items": room_detail_items(strengths, empty="No clear surplus room"),
            },
            {
                "label": "Health Outlook",
                "value": health_flag,
                "note": (
                    truncate_text(key_injuries_summary, 90)
                    if key_injuries_summary
                    else (
                        "Current injury updates are incomplete or stale."
                        if "uncertain" in _safe_text(health_flag).lower()
                        else "No current high-value injury concern."
                    )
                ),
                "tone": "risk",
                "detail_items_title": "Injury Context",
                "detail_items": health_detail_items(),
            },
        ]
    )

    render_section_header(
        "Roster Decisions",
        kicker="Keep, move, cut",
        note="Core assets stay visible first. Secondary trade, hold, and cut lists are grouped below to keep mobile scanning tighter.",
    )
    show_generic_roster_decisions = not my_roster_limit.get("over_limit")
    if not show_generic_roster_decisions:
        st.caption("Urgent move, trade-away, and cut recommendations are owned by the roster-limit alert above until you are back under the Sleeper limit.")

    render_player_scan_cards(
        core_assets_df,
        score_field="value_score",
        title="Core Assets",
        note="Best current anchors under your active team lens.",
        max_items=min(len(core_assets_df), 6) if not core_assets_df.empty else 0,
        status_label="Core Asset",
        extra_tags_fn=lambda row: ["Core"] if _safe_text(row.get("role")) == "Core" else [],
        compact=True,
        enable_quick_view=True,
        quick_view_source_label="My Team - Core Assets",
        quick_view_key_prefix=f"my_team_core_assets_{selected_league_id}_{my_roster_id}",
    )

    with st.expander("Protected players and secondary decisions", expanded=False):
        if untouchables_df.empty:
            st.markdown("#### Untouchables")
            st.caption("No untouchables are set right now. Use Deep Analysis if you want to lock specific players.")
        else:
            render_player_scan_cards(
                untouchables_df,
                score_field="value_score",
                title="Untouchables",
                note="Manual no-trade protections from your current roster plan.",
                max_items=min(len(untouchables_df), 6),
                status_label="Untouchable",
                extra_tags_fn=lambda row: ["Untouchable"],
                compact=True,
                enable_quick_view=True,
                quick_view_source_label="My Team - Untouchables",
                quick_view_key_prefix=f"my_team_untouchables_{selected_league_id}_{my_roster_id}",
            )

        if not is_premium:
            if render_premium_lock is not None:
                render_premium_lock(
                    "Advanced roster decisions",
                    "Trade-away, hold, and drop candidate lists with player-level reasoning.",
                    feature="Premium My Team",
                )
            show_generic_roster_decisions = False

        if show_generic_roster_decisions:
            if trade_candidates_df.empty:
                st.markdown("#### Trade Candidates")
                st.caption("No obvious move-out candidates are standing above the rest right now.")
            else:
                render_player_scan_cards(
                    trade_candidates_df,
                    score_field="value_score",
                    title="Trade Candidates",
                    note="Assets you can move without undercutting the current roster plan.",
                    max_items=min(len(trade_candidates_df), 6),
                    status_label="Trade Candidate",
                    note_fn=lambda row: trade_note_map.get(str(row.get("player_id"))) or trade_note_map.get(player_display_name(row)) or trade_note_map.get(_safe_text(row.get("name"))),
                    compact=True,
                    show_inline_reason=True,
                    enable_quick_view=True,
                    quick_view_source_label="My Team - Trade Candidates",
                    quick_view_key_prefix=f"my_team_trade_candidates_{selected_league_id}_{my_roster_id}",
                    enable_feedback=True,
                    feedback_recommendation_type="trade_candidate",
                )

            if hold_candidates_df.empty:
                st.markdown("#### Hold Candidates")
                st.caption("No special hold-pressure candidates are standing out unless roster pressure increases.")
            else:
                render_player_scan_cards(
                    hold_candidates_df,
                    score_field="value_score",
                    title="Hold Candidates",
                    note="Low-value players still worth protecting because of upside, need, or roster context.",
                    max_items=min(len(hold_candidates_df), 6),
                    status_label="Hold",
                    note_fn=lambda row: hold_note_map.get(str(row.get("player_id"))) or hold_note_map.get(player_display_name(row)) or hold_note_map.get(_safe_text(row.get("name"))),
                    compact=True,
                    show_inline_reason=True,
                    enable_quick_view=True,
                    quick_view_source_label="My Team - Hold Candidates",
                    quick_view_key_prefix=f"my_team_hold_candidates_{selected_league_id}_{my_roster_id}",
                    enable_feedback=True,
                    feedback_recommendation_type="hold_candidate",
                )

            if drop_candidates_df.empty:
                st.markdown("#### Drop Candidates")
                st.caption("No immediate cut stands out right now. That is a good sign unless your roster size changes.")
            else:
                render_player_scan_cards(
                    drop_candidates_df,
                    score_field="value_score",
                    title="Drop Candidates",
                    note="Lowest-utility cuts if you need to clear room quickly.",
                    max_items=min(len(drop_candidates_df), 6),
                    status_label="Drop Candidate",
                    note_fn=lambda row: drop_note_map.get(str(row.get("player_id"))) or drop_note_map.get(player_display_name(row)) or drop_note_map.get(_safe_text(row.get("name"))),
                    compact=True,
                    show_inline_reason=True,
                    enable_quick_view=True,
                    quick_view_source_label="My Team - Drop Candidates",
                    quick_view_key_prefix=f"my_team_drop_candidates_{selected_league_id}_{my_roster_id}",
                    enable_feedback=True,
                    feedback_recommendation_type="drop_candidate",
                )

    render_roster_utility_debug(
        my_roster_limit.get("lowest_utility_candidates"),
        title="Decision Debug: Bottom 15 roster utility candidates",
    )
    render_no_team_player_debug(
        my_roster_limit.get("rostered_no_team_players"),
        title="Decision Debug: Rostered No-Team / FA Players",
    )

    render_section_header(
        "Lineup & Depth",
        kicker="Roster construction",
        note="Projected starters stay visible. Bench detail is collapsed below for mobile scanning.",
    )
    render_player_scan_cards(
        starters.sort_values("value_score", ascending=False),
        score_field="value_score",
        title="Projected Starters",
        note="Most important weekly lineup pieces under the current role and strategy lens.",
        max_items=min(len(starters), 10),
        show_slot=True,
        status_label="Starter",
        extra_tags_fn=lambda row: ["Starter"],
        compact=True,
        enable_quick_view=True,
        quick_view_source_label="My Team - Projected Starters",
        quick_view_key_prefix=f"my_team_projected_starters_{selected_league_id}_{my_roster_id}",
    )
    if not key_backups_df.empty:
        if is_premium:
            with st.expander("Key backups", expanded=False):
                render_player_scan_cards(
                    key_backups_df,
                    score_field="value_score",
                    title="Key Backups",
                    note="First bench players who become meaningful if injuries or lineup changes hit.",
                    max_items=min(len(key_backups_df), 6),
                    status_label="Hold",
                    extra_tags_fn=lambda row: ["Bench"] if _safe_text(row.get("role")) == "Bench" else [],
                    compact=True,
                    enable_quick_view=True,
                    quick_view_source_label="My Team - Key Backups",
                    quick_view_key_prefix=f"my_team_key_backups_{selected_league_id}_{my_roster_id}",
                )
        elif render_premium_lock is not None:
            render_premium_lock(
                "Bench insulation detail",
                "Key backup and depth insulation reads.",
                feature="Premium My Team",
            )

    render_section_header(
        "Team Outlook",
        kicker="Short and clear",
        note="Keep this concise: direction, ranks, and current health trust.",
    )
    render_summary_tiles(
        [
            {
                "label": "Strategy",
                "value": active_team_strategy_label,
                "note": f"Auto detected: {team_strategy_label(auto_team_strategy)}",
                "tone": "strategy",
                "detail": "Team strategy is the active recommendation lens used to frame trades, roster pressure, and risk tolerance.",
                "supporting_context": f"Auto detected: {team_strategy_label(auto_team_strategy)}",
            },
            {
                "label": "Archetype",
                "value": _safe_text(team_row.get("archetype_label"), "Unclassified"),
                "note": truncate_text(_safe_text(team_row.get("archetype_explanation")), 100),
                "tone": "franchise",
                "detail": _safe_text(team_row.get("archetype_explanation"), "This roster does not have enough archetype evidence yet."),
                "detail_items_title": "Archetype Inputs",
                "detail_items": [
                    {"title": item, "note": "Strength"} for item in safe_list(team_row.get("archetype_strengths"))[:3]
                ] + [
                    {"title": item, "note": "Risk"} for item in safe_list(team_row.get("archetype_risks"))[:3]
                ],
            },
            {
                "label": "Power Rank",
                "value": format_rank(team_row.get("power_rank")),
                "note": f"Current strength | starter rank {format_rank(team_row.get('starter_rank'))}",
                "tone": "power",
                "detail_items_title": "Current Power Board",
                "detail_items": rank_detail_items("power_rank", "power_score"),
            },
            {
                "label": "Franchise Rank",
                "value": format_rank(team_row.get("franchise_rank")),
                "note": f"Draft rank {format_rank(team_row.get('draft_capital_rank'))} | age rank {format_rank(team_row.get('age_rank'))}",
                "tone": "franchise",
                "detail_items_title": "Franchise Value Board",
                "detail_items": rank_detail_items("franchise_rank", "franchise_score"),
                "supporting_context": (
                    f"Draft rank {format_rank(team_row.get('draft_capital_rank'))}; "
                    f"age rank {format_rank(team_row.get('age_rank'))}; "
                    f"roster value rank {format_rank(team_row.get('roster_value_rank'))}."
                ),
            },
            {
                "label": "Health Outlook",
                "value": health_flag,
                "note": f"{injured_starters} injured projected starter{'s' if injured_starters != 1 else ''}.",
                "tone": "risk",
                "detail_items_title": "Injury Context",
                "detail_items": health_detail_items(),
            },
        ]
    )
