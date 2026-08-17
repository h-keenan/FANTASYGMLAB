from html import escape
from typing import Any, Callable

import pandas as pd
import streamlit as st

from modules import canonical_player_ranking
from modules import canonical_recommendation_narrative
from modules import league_format_context
from modules import workspace_ui
from modules.html_rendering import inject_global_styles
from modules.my_team_decision_styles import MY_TEAM_DECISION_CSS
from modules.roster_room_presentation import canonicalize_surplus_and_thin

from modules.ui_primitives import (
    render_empty_state_panel,
    render_section_header as render_canonical_section_header,
)


POSITION_GROUPS = (
    ("QB", ("QB",)),
    ("RB", ("RB",)),
    ("WR", ("WR",)),
    ("TE", ("TE",)),
    ("Flex", ("FLEX", "SUPER_FLEX", "WR/RB")),
    ("Special Teams", ("K", "DEF", "DST")),
)


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


def _roster_scan_narrative(
    row,
    *,
    action: str,
    reason: str,
    league_id: str,
    roster_id: str,
    valuation_lens: str,
    source_surface: str,
) -> dict:
    return canonical_recommendation_narrative.build_roster_decision_narrative(
        {
            "player_id": row.get("player_id"),
            "name": row.get("name"),
            "reason": reason,
        },
        action=action,
        league_id=league_id,
        roster_id=_safe_text(roster_id),
        valuation_lens=valuation_lens,
        source_surface=source_surface,
    ).to_dict()


def _strategy_panel_key(league_id: str, roster_id) -> str:
    return f"my_team_strategy_panel_{_safe_text(league_id)}_{_safe_text(roster_id)}"


def strategy_identity_html(
    *,
    strategy_label: str,
    archetype_label: str,
    auto_strategy_label: str,
) -> str:
    """Single owner for strategy + construction diagnosis (presentation only)."""

    strategy = _safe_text(strategy_label, "Unclassified")
    archetype = _safe_text(archetype_label)
    auto_label = _safe_text(auto_strategy_label)
    support_parts: list[str] = []
    if archetype and archetype.casefold() != strategy.casefold():
        support_parts.append(archetype)
    if auto_label and auto_label.casefold() != strategy.casefold():
        support_parts.append(f"Auto read: {auto_label}")
    support = " · ".join(support_parts)
    return (
        "<section class='my-team-strategy-identity' aria-label='Team strategy'>"
        "<div class='my-team-strategy-kicker'>Team strategy</div>"
        f"<div class='my-team-strategy-primary'>{escape(strategy)}</div>"
        + (
            f"<div class='my-team-strategy-support'>{escape(support)}</div>"
            if support
            else ""
        )
        + "<p class='my-team-strategy-note'>"
        "Strategy is the ranking lens. Archetype is the construction diagnosis — not a second strategy chip."
        "</p>"
        "</section>"
    )


def _canonical_header(title: str, *, eyebrow: str = "", subtitle: str = "") -> None:
    render_canonical_section_header(
        title,
        eyebrow=eyebrow,
        subtitle=subtitle,
        heading_level=2,
    )


def _render_empty_roster_section(title: str, explanation: str) -> None:
    render_empty_state_panel(
        title,
        explanation,
        kind="no-data",
        recovery_guidance="No roster calculation or recommendation is changed by this empty state.",
    )


def _starter_groups(starters: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Partition projected starters once, preserving their existing row data."""

    if starters is None or starters.empty:
        return []
    slots = starters.get("slot", pd.Series("", index=starters.index)).astype(str).str.upper()
    positions = starters.get("position", pd.Series("", index=starters.index)).astype(str).str.upper()
    claimed = pd.Series(False, index=starters.index)
    groups: list[tuple[str, pd.DataFrame]] = []
    for label, group_slots in POSITION_GROUPS:
        mask = slots.isin(group_slots)
        if label != "Flex":
            mask |= slots.eq("") & positions.isin(group_slots)
        mask &= ~claimed
        if mask.any():
            groups.append((label, starters.loc[mask].copy()))
            claimed |= mask
    remaining = starters.loc[~claimed].copy()
    if not remaining.empty:
        groups.append(("Other Starters", remaining))
    return groups


_ROUND_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th"}


def _round_label(round_num: int) -> str:
    if round_num in _ROUND_ORDINALS:
        return _ROUND_ORDINALS[round_num]
    return f"R{round_num}" if round_num > 0 else "?"


def room_outlook_label(
    *,
    position: str,
    classification: str,
    strengths: list | tuple | None,
    upgrade_opportunity: bool = False,
    temporary_injury_pressure: bool = False,
) -> str:
    """Map existing need classifications to plain roster language.

    Presentation only — does not invent coverage thresholds.
    """

    pos = _safe_text(position).upper()
    strength_set = {
        _safe_text(item).upper() for item in (strengths or []) if _safe_text(item)
    }
    if pos in strength_set:
        return "Strength"
    kind = _safe_text(classification).strip().lower()
    if kind == "short_term_need":
        return "Thin"
    if kind == "future_risk":
        return "Future risk"
    if upgrade_opportunity:
        return "Upgrade room"
    if temporary_injury_pressure:
        return "Injury pressure"
    return "Covered"


def compact_owned_draft_capital(
    draft_picks: list[dict] | None,
    roster_id,
) -> list[dict[str, Any]]:
    """Group owned future picks by season for compact My Team display."""

    owned: list[dict] = []
    roster_key = str(roster_id)
    for pick in draft_picks or []:
        if str(pick.get("owner_roster_id")) != roster_key:
            continue
        season = _safe_positive_int(pick.get("season"), 0)
        round_num = _safe_positive_int(pick.get("round"), 0)
        if not season or not round_num:
            continue
        owned.append({"season": season, "round": round_num})
    if not owned:
        return []
    by_season: dict[int, list[int]] = {}
    for item in owned:
        by_season.setdefault(int(item["season"]), []).append(int(item["round"]))
    rows: list[dict[str, Any]] = []
    for season in sorted(by_season):
        rounds = sorted(by_season[season])
        rows.append(
            {
                "season": season,
                "rounds": rounds,
                "label": " · ".join(_round_label(round_num) for round_num in rounds),
            }
        )
    return rows


def build_construction_observations(
    *,
    strengths: list | tuple | None,
    weaknesses: list | tuple | None,
    team_row,
    health_flag: str,
    draft_capital_rank,
    format_rank: Callable,
    league_settings: dict | None = None,
) -> list[dict[str, str]]:
    """Two or three roster observations from existing canonical signals only."""

    observations: list[dict[str, str]] = []
    strength_rooms = [_safe_text(item).upper() for item in (strengths or []) if _safe_text(item)]
    pressure_rooms = [_safe_text(item).upper() for item in (weaknesses or []) if _safe_text(item)]
    archetype_strengths = team_row.get("archetype_strengths") if hasattr(team_row, "get") else None
    if not isinstance(archetype_strengths, list):
        archetype_strengths = []

    if strength_rooms:
        observations.append(
            {
                "label": "Strength",
                "title": f"{' / '.join(strength_rooms[:2])} foundation",
                "body": "Existing team metrics mark this room as a relative strength.",
                "tone": "strength",
            }
        )
    elif archetype_strengths:
        observations.append(
            {
                "label": "Strength",
                "title": _safe_text(archetype_strengths[0], "Roster foundation"),
                "body": _safe_text(
                    team_row.get("archetype_label"),
                    "Existing archetype read",
                ),
                "tone": "strength",
            }
        )

    if pressure_rooms:
        observations.append(
            {
                "label": "Pressure point",
                "title": f"{' / '.join(pressure_rooms[:2])} coverage",
                "body": "Short-term coverage need from the existing roster-needs assessment.",
                "tone": "need",
            }
        )
    elif "uncertain" in _safe_text(health_flag).lower() or (
        _safe_text(health_flag) and _safe_text(health_flag).lower() not in {"stable", "healthy", ""}
    ):
        observations.append(
            {
                "label": "Pressure point",
                "title": "Health outlook",
                "body": _safe_text(health_flag, "Injury context needs attention."),
                "tone": "health",
            }
        )

    capital_rank = _safe_positive_int(draft_capital_rank, 0)
    if (
        capital_rank
        and capital_rank <= 4
        and league_format_context.lead_with_franchise_construction(league_settings)
    ):
        observations.append(
            {
                "label": "Future flexibility",
                "title": f"Draft capital {format_rank(capital_rank)}",
                "body": "Above-average owned picks give more roster optionality.",
                "tone": "opportunity",
            }
        )
    return observations[:3]


def _position_groups_items(
    team_needs_assessment,
    *,
    strengths: list | tuple | None,
    league_settings: dict | None,
) -> list[dict[str, str]]:
    settings = league_settings or {}
    superflex = (
        int(settings.get("superflex_count") or 0) > 0
        or int(settings.get("qb_count") or 1) >= 2
        or str(settings.get("qb_format") or "").strip().lower()
        in {"2qb", "superflex"}
    )
    te_premium = bool(settings.get("te_premium"))
    items: list[dict[str, str]] = []
    positions = getattr(team_needs_assessment, "positions", ()) or ()
    for assessment in positions:
        position = _safe_text(getattr(assessment, "position", "")).upper()
        if not position:
            continue
        label = room_outlook_label(
            position=position,
            classification=_safe_text(getattr(assessment, "classification", "")),
            strengths=strengths,
            upgrade_opportunity=bool(getattr(assessment, "upgrade_opportunity", False)),
            temporary_injury_pressure=bool(
                getattr(assessment, "temporary_injury_pressure", False)
            ),
        )
        reasons = getattr(assessment, "reasons", ()) or ()
        body = _safe_text(reasons[0]) if reasons else "Existing coverage assessment."
        context_bits = []
        if position == "QB" and superflex:
            context_bits.append("Superflex")
        elif position == "QB":
            context_bits.append("1QB")
        if position == "TE" and te_premium:
            context_bits.append("TE Premium")
        title = position if not context_bits else f"{position} · {' · '.join(context_bits)}"
        tone = {
            "Strength": "strength",
            "Thin": "need",
            "Future risk": "need",
            "Upgrade room": "opportunity",
            "Injury pressure": "health",
        }.get(label, "strategy")
        items.append(
            {
                "label": label,
                "title": title,
                "body": body,
                "tone": tone,
            }
        )
    return items


def _draft_capital_html(
    capital_rows: list[dict[str, Any]],
    *,
    draft_capital_rank,
    format_rank: Callable,
) -> str:
    if not capital_rows:
        rank_note = (
            f" League draft-capital rank {escape(format_rank(draft_capital_rank))}."
            if _safe_positive_int(draft_capital_rank, 0)
            else ""
        )
        return (
            "<div class='advice-card dg-ui-card'>"
            "<div class='advice-label'>Draft Capital</div>"
            "<div class='advice-title'>No owned future picks on file</div>"
            f"<div class='advice-body'>Pick ownership is empty for this roster right now.{rank_note}</div>"
            "</div>"
        )
    rows_html = []
    for row in capital_rows:
        rows_html.append(
            "<div class='advice-card dg-ui-card'>"
            f"<div class='advice-label'>{escape(str(row.get('season')))}</div>"
            f"<div class='advice-title'>{escape(_safe_text(row.get('label')))}</div>"
            "<div class='advice-body'>Owned picks for this draft year.</div>"
            "</div>"
        )
    rank_caption = ""
    if _safe_positive_int(draft_capital_rank, 0):
        rank_caption = (
            f"<p class='dg-client-disclosure-body'>Draft capital rank "
            f"{escape(format_rank(draft_capital_rank))} in the league. "
            "Full board comparison lives on League Overview.</p>"
        )
    return "<div class='advice-grid'>" + "".join(rows_html) + "</div>" + rank_caption


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
    strongest_surplus_raw = list(limit_context.get("strongest_surplus_positions") or [])
    thinnest_raw = list(limit_context.get("thinnest_positions") or [])
    needed = list(limit_context.get("needed_positions") or [])
    strongest_surplus_list, thinnest_list = canonicalize_surplus_and_thin(
        strongest_surplus_raw, thinnest_raw, needed=needed
    )
    strongest_surplus = ", ".join(strongest_surplus_list) or "None"
    thinnest_positions = ", ".join(thinnest_list) or "None"
    replaceable_lineup_needs = ", ".join(
        limit_context.get("replaceable_lineup_needs") or []
    )
    thin_notes = limit_context.get("thinnest_position_notes") or {}
    thin_note = " | ".join(
        _safe_text(thin_notes.get(position))
        for position in thinnest_list[:2]
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
        + "<div class='dg-alert-kicker'>"
        + workspace_ui.semantic_icon_html("health", label="Roster Pressure")
        + "Roster Pressure</div>"
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
        + "<span>Active</span>"
        + f"<strong>{current_size}/{max_size}</strong>"
        + f"<small>{escape(roster_note)}</small>"
        + "</div>"
        + "<div class='roster-limit-stat roster-limit-stat-danger'>"
        + "<span>Over</span>"
        + f"<strong>{over_by}</strong>"
        + "<small>Slots to clear</small>"
        + "</div>"
        + "<div class='roster-limit-stat'>"
        + "<span>Surplus</span>"
        + f"<strong>{escape(strongest_surplus)}</strong>"
        + "<small>Best rooms to shop</small>"
        + "</div>"
        + "<div class='roster-limit-stat roster-limit-stat-warning'>"
        + "<span>Protect</span>"
        + f"<strong>{escape(thinnest_positions)}</strong>"
        + f"<small>{escape(thin_copy)}</small>"
        + "</div>"
        + "<div class='roster-limit-stat'>"
        + "<span>Taxi / IR</span>"
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
            "title": "Lowest-impact cuts",
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
            "<div class='advice-card dg-ui-card"
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
                "<div class='prospect-card dg-ui-card'>"
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
    biggest_need_label: str = "Biggest Need",
    biggest_need_value: str,
    biggest_need_note: str,
    trade_target_value: str,
    trade_opportunity_note: str,
    trade_target_row,
    trade_recommendation_narrative: dict | None = None,
    waiver_value: str,
    waiver_note: str,
    top_waiver,
    waiver_recommendation_narrative: dict | None = None,
    next_move_recommendation_narrative: dict | None = None,
    roster_limit_value: str,
    roster_limit_note: str,
    injury_alert_value: str,
    injury_alert_note: str,
    immediate_value: str,
    immediate_note: str,
    immediate_tone: str,
    next_move_shop_player_id: str = "",
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
    team_needs_assessment=None,
    draft_pick_assets: list | None = None,
    league_settings: dict | None = None,
    advice_items: list | None = None,
    render_strategy_management: Callable | None = None,
) -> None:
    inject_global_styles(MY_TEAM_DECISION_CSS)
    auto_label = team_strategy_label(auto_team_strategy)
    archetype_label = _safe_text(
        team_row.get("archetype_label") if hasattr(team_row, "get") else "",
        "",
    )
    panel_key = _strategy_panel_key(selected_league_id, my_roster_id)
    with st.container(key="my_team_strategy_gateway"):
        st.markdown(
            strategy_identity_html(
                strategy_label=active_team_strategy_label,
                archetype_label=archetype_label,
                auto_strategy_label=auto_label,
            ),
            unsafe_allow_html=True,
        )
        toggle_label = (
            "Hide strategy & analysis"
            if st.session_state.get(panel_key)
            else "Strategy & analysis"
        )

        def _toggle_strategy_panel() -> None:
            st.session_state[panel_key] = not bool(st.session_state.get(panel_key))

        st.button(
            toggle_label,
            key=f"{panel_key}_toggle",
            on_click=_toggle_strategy_panel,
            use_container_width=True,
        )
        if st.session_state.get(panel_key):
            with st.container(key="my_team_strategy_panel"):
                if render_strategy_management is not None:
                    render_strategy_management()
                elif render_premium_lock is not None:
                    render_premium_lock(
                        "Strategy & analysis",
                        "Team strategy, untouchables, roles, and outlook stay on this roster — Premium unlocks the controls.",
                        feature="Premium My Team",
                    )
                else:
                    st.caption("Strategy controls are unavailable on this path.")

    how_to_read = workspace_ui.client_disclosure_html(
        "How these roster grades work",
        workspace_ui.concept_band_html(
            [
                {
                    "label": "Strategy",
                    "title": "One ranking lens",
                    "body": "The top strategy line is the ranking lens. Archetype is the construction diagnosis shown as supporting copy — not a second Contender chip.",
                    "tone": "strategy",
                    "hide_icon": True,
                },
                {
                    "label": "Core",
                    "title": "Projected roster core",
                    "body": "Optimal lineup projection from existing values — not live Sleeper starter locks.",
                    "tone": "power",
                    "hide_icon": True,
                },
                {
                    "label": "Actions",
                    "title": "Handoffs",
                    "body": "Trade Hub, Waivers, and Player Quick View own the prescriptions.",
                    "tone": "opportunity",
                    "hide_icon": True,
                },
            ]
        ),
    )
    if how_to_read:
        st.markdown(how_to_read, unsafe_allow_html=True)

    _canonical_header("Roster Signals")
    posture_comparisons: dict[str, dict] = {}
    if league_rank_rows is not None and not getattr(league_rank_rows, "empty", True):
        try:
            from modules import comparative_metrics

            posture_comparisons = comparative_metrics.dashboard_comparison_payloads(
                league_rank_rows,
                my_roster_id,
            )
        except Exception:
            posture_comparisons = {}
    show_franchise_construction = league_format_context.lead_with_franchise_construction(
        league_settings
    )
    posture_items = [
        {
            "label": "Power",
            "title": format_rank(team_row.get("power_rank")),
            "body": f"Starter unit {format_rank(team_row.get('starter_rank'))}",
            "tone": "power",
            "comparison": posture_comparisons.get("Power Rank"),
            "tappable": bool(posture_comparisons.get("Power Rank")),
            "hide_icon": True,
        },
    ]
    if show_franchise_construction:
        posture_items.append(
            {
                "label": "Franchise",
                "title": format_rank(team_row.get("franchise_rank")),
                "body": (
                    f"Draft capital {format_rank(team_row.get('draft_capital_rank'))}"
                    f" · Age {format_rank(team_row.get('age_rank'))}"
                ),
                "tone": "franchise",
                "comparison": posture_comparisons.get("Franchise Rank"),
                "tappable": bool(posture_comparisons.get("Franchise Rank")),
                "hide_icon": True,
            },
        )
    # Keep league_rank_rows live — used above for clickable Power/Franchise comparisons.
    _ = (truncate_text, injured_starters, key_injuries_summary, format_score)
    with st.container(key="my_team_roster_signals"):
        render_summary_tiles(
            workspace_ui.concept_items_as_summary_tiles(posture_items),
            compact=True,
            key_prefix=f"my_team_signals_{selected_league_id}_{my_roster_id}",
        )

    observations = build_construction_observations(
        strengths=strengths,
        weaknesses=weaknesses,
        team_row=team_row,
        health_flag=health_flag,
        draft_capital_rank=team_row.get("draft_capital_rank") if hasattr(team_row, "get") else None,
        format_rank=format_rank,
        league_settings=league_settings,
    )
    if observations:
        _canonical_header("Strength & Pressure")
        render_advice_cards(
            [
                {
                    "label": item["label"],
                    "title": item["title"],
                    "body": item["body"],
                    "primary": index == 0,
                }
                for index, item in enumerate(observations)
            ]
        )

    _canonical_header("Roster Decisions")
    show_generic_roster_decisions = not my_roster_limit.get("over_limit")
    if not show_generic_roster_decisions:
        st.caption(
            "Urgent move, trade-away, and cut recommendations are owned by the roster-limit alert above until you are back under the Sleeper limit."
        )

    with st.container(key="my_team_roster_decisions"):
        if untouchables_df.empty:
            _render_empty_roster_section(
                "No untouchables set",
                "Open Strategy & analysis to protect specific players from trade recommendations.",
            )
        else:
            with st.container(key="my_team_decisions_untouchables"):
                render_canonical_section_header(
                    "Untouchables",
                    subtitle="Manual no-trade protections from your current roster plan.",
                    heading_level=3,
                )
                render_player_scan_cards(
                    untouchables_df,
                    score_field=score_field,
                    title="Untouchables",
                    note="Manual no-trade protections from your current roster plan.",
                    max_items=min(len(untouchables_df), 6),
                    status_label="Untouchable",
                    extra_tags_fn=lambda row: ["Untouchable"],
                    compact=True,
                    enable_quick_view=True,
                    quick_view_source_label="My Team - Untouchables",
                    quick_view_key_prefix=f"my_team_untouchables_{selected_league_id}_{my_roster_id}",
                    show_header=False,
                    design_system=True,
                    show_prestige=False,
                    reason_limit=90,
                )

        if not is_premium:
            if render_premium_lock is not None:
                render_premium_lock(
                    "Advanced roster decisions",
                    "Trade-away, hold, and drop lists with player-level reasoning when starters alone are not enough.",
                    feature="Premium My Team",
                )
            show_generic_roster_decisions = False

        def _trade_scan_narrative(row):
            reason = (
                trade_note_map.get(str(row.get("player_id")))
                or trade_note_map.get(player_display_name(row))
                or trade_note_map.get(_safe_text(row.get("name")))
                or ""
            )
            return _roster_scan_narrative(
                row,
                action="Trade Candidate",
                reason=reason,
                league_id=selected_league_id,
                roster_id=my_roster_id,
                valuation_lens=score_field,
                source_surface="my_team_trade_candidate",
            )

        def _hold_scan_narrative(row):
            reason = (
                hold_note_map.get(str(row.get("player_id")))
                or hold_note_map.get(player_display_name(row))
                or hold_note_map.get(_safe_text(row.get("name")))
                or ""
            )
            return _roster_scan_narrative(
                row,
                action="Hold",
                reason=reason,
                league_id=selected_league_id,
                roster_id=my_roster_id,
                valuation_lens=score_field,
                source_surface="my_team_hold_candidate",
            )

        def _drop_scan_narrative(row):
            reason = (
                drop_note_map.get(str(row.get("player_id")))
                or drop_note_map.get(player_display_name(row))
                or drop_note_map.get(_safe_text(row.get("name")))
                or ""
            )
            return _roster_scan_narrative(
                row,
                action="Drop Candidate",
                reason=reason,
                league_id=selected_league_id,
                roster_id=my_roster_id,
                valuation_lens=score_field,
                source_surface="my_team_drop_candidate",
            )

        if show_generic_roster_decisions:
            if trade_candidates_df.empty:
                _render_empty_roster_section(
                    "No trade candidates",
                    "No obvious move-out candidate stands above the rest right now.",
                )
            else:
                with st.container(key="my_team_decisions_trade"):
                    render_canonical_section_header(
                        "Trade Candidates",
                        subtitle="Assets you can move without undercutting the current roster plan.",
                        heading_level=3,
                    )
                    render_player_scan_cards(
                        trade_candidates_df,
                        score_field=score_field,
                        title="Trade Candidates",
                        note="Assets you can move without undercutting the current roster plan.",
                        max_items=min(len(trade_candidates_df), 6),
                        status_label="Trade Candidate",
                        extra_tags_fn=lambda row: ["Trade Candidate"],
                        note_fn=lambda row: trade_note_map.get(str(row.get("player_id")))
                        or trade_note_map.get(player_display_name(row))
                        or trade_note_map.get(_safe_text(row.get("name"))),
                        recommendation_narrative_fn=_trade_scan_narrative,
                        compact=True,
                        show_inline_reason=True,
                        enable_quick_view=True,
                        quick_view_source_label="My Team - Trade Candidates",
                        quick_view_key_prefix=f"my_team_trade_candidates_{selected_league_id}_{my_roster_id}",
                        enable_feedback=True,
                        feedback_recommendation_type="trade_candidate",
                        show_header=False,
                        design_system=True,
                        show_prestige=False,
                        reason_limit=160,
                    )

            if hold_candidates_df.empty:
                _render_empty_roster_section(
                    "No priority holds",
                    "No special hold-pressure candidate stands out unless roster pressure increases.",
                )
            else:
                with st.container(key="my_team_decisions_hold"):
                    render_canonical_section_header(
                        "Hold Candidates",
                        subtitle="Players worth protecting because of upside, need, or roster context.",
                        heading_level=3,
                    )
                    render_player_scan_cards(
                        hold_candidates_df,
                        score_field=score_field,
                        title="Hold Candidates",
                        note="Low-value players still worth protecting because of upside, need, or roster context.",
                        max_items=min(len(hold_candidates_df), 6),
                        status_label="Hold",
                        extra_tags_fn=lambda row: ["Hold"],
                        note_fn=lambda row: hold_note_map.get(str(row.get("player_id")))
                        or hold_note_map.get(player_display_name(row))
                        or hold_note_map.get(_safe_text(row.get("name"))),
                        recommendation_narrative_fn=_hold_scan_narrative,
                        compact=True,
                        show_inline_reason=True,
                        enable_quick_view=True,
                        quick_view_source_label="My Team - Hold Candidates",
                        quick_view_key_prefix=f"my_team_hold_candidates_{selected_league_id}_{my_roster_id}",
                        enable_feedback=True,
                        feedback_recommendation_type="hold_candidate",
                        show_header=False,
                        design_system=True,
                        show_prestige=False,
                        reason_limit=90,
                    )

            if drop_candidates_df.empty:
                _render_empty_roster_section(
                    "No drop candidates",
                    "No immediate cut stands out. Revisit this section if your roster size changes.",
                )
            else:
                with st.container(key="my_team_decisions_drop"):
                    render_canonical_section_header(
                        "Drop Candidates",
                        subtitle="Clearest drop candidates if you need to clear room quickly.",
                        heading_level=3,
                    )
                    render_player_scan_cards(
                        drop_candidates_df,
                        score_field=score_field,
                        title="Drop Candidates",
                        note="Clearest drop candidates if you need to clear room quickly.",
                        max_items=min(len(drop_candidates_df), 6),
                        status_label="Drop Candidate",
                        extra_tags_fn=lambda row: ["Drop Candidate"],
                        note_fn=lambda row: drop_note_map.get(str(row.get("player_id")))
                        or drop_note_map.get(player_display_name(row))
                        or drop_note_map.get(_safe_text(row.get("name"))),
                        recommendation_narrative_fn=_drop_scan_narrative,
                        compact=True,
                        show_inline_reason=True,
                        enable_quick_view=True,
                        quick_view_source_label="My Team - Drop Candidates",
                        quick_view_key_prefix=f"my_team_drop_candidates_{selected_league_id}_{my_roster_id}",
                        enable_feedback=True,
                        feedback_recommendation_type="drop_candidate",
                        show_header=False,
                        design_system=True,
                        show_prestige=False,
                        reason_limit=80,
                    )

    _canonical_header("Roster Actions")
    action_tiles = [
        *(
            []
            if my_roster_limit.get("over_limit")
            else [
                {
                    "label": "Next Move",
                    "value": immediate_value,
                    "note": (
                        canonical_recommendation_narrative.shorten_narrative_text(
                            (next_move_recommendation_narrative or {}).get("reason")
                            or immediate_note,
                            150,
                        )
                        if next_move_recommendation_narrative
                        else immediate_note
                    ),
                    "tone": immediate_tone,
                    "wide": True,
                    "recommendation_narrative": next_move_recommendation_narrative,
                    **(
                        {
                            "route_key": "trade_hub",
                            "route_player_id": next_move_shop_player_id,
                            "route_focus_mode": "my_player",
                        }
                        if next_move_shop_player_id
                        else {}
                    ),
                }
            ]
        ),
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
        {
            "label": biggest_need_label,
            "value": biggest_need_value,
            "note": biggest_need_note,
            "tone": "need",
        },
        {
            "label": "Top Trade Opportunity",
            "value": trade_target_value,
            "note": (
                canonical_recommendation_narrative.shorten_narrative_text(
                    (trade_recommendation_narrative or {}).get("reason")
                    or trade_opportunity_note,
                    150,
                )
                if trade_recommendation_narrative
                else trade_opportunity_note
            ),
            "tone": "trade",
            "player_row": trade_target_row,
            "recommendation_label": (
                _safe_text((trade_recommendation_narrative or {}).get("action"))
                or "Trade Target"
            ),
            "score_field": score_field,
            "route_key": "trade_hub",
            "route_player_id": (
                _safe_text(trade_target_row.get("player_id"))
                if trade_target_row is not None and hasattr(trade_target_row, "get")
                else ""
            ),
            "route_focus_mode": "target_player",
            "recommendation_id": _safe_text(
                (trade_recommendation_narrative or {}).get("recommendation_id")
            ),
            "recommendation_narrative": trade_recommendation_narrative,
        },
        {
            "label": "Top Waiver Opportunity",
            "value": waiver_value,
            "note": (
                canonical_recommendation_narrative.shorten_narrative_text(
                    (waiver_recommendation_narrative or {}).get("reason")
                    or waiver_note,
                    150,
                )
                if waiver_recommendation_narrative
                else waiver_note
            ),
            "tone": "waiver",
            "player_row": top_waiver if top_waiver is not None and not top_waiver.empty else None,
            "recommendation_label": (
                _safe_text((waiver_recommendation_narrative or {}).get("action"))
                or "Priority Add"
            ),
            "score_field": score_field,
            "route_key": "waivers",
            "route_player_id": (
                _safe_text(top_waiver.get("player_id"))
                if top_waiver is not None
                and hasattr(top_waiver, "get")
                and not getattr(top_waiver, "empty", False)
                else ""
            ),
            "recommendation_narrative": waiver_recommendation_narrative,
        },
    ]
    with st.container(key="my_team_roster_actions"):
        render_home_command_tiles(action_tiles)
    if my_roster_limit.get("over_limit"):
        render_roster_limit_alert(my_roster_limit, compact=True)

    _canonical_header("Roster Core")
    st.caption(
        "Projected roster core from existing player values and league roster settings — "
        "not a live Sleeper starting-lineup lock."
    )
    starter_groups = _starter_groups(starters)
    with st.container(key="my_team_roster_core"):
        if not starter_groups:
            _render_empty_roster_section(
                "No projected core",
                "A projected core could not be formed from the current roster and league settings.",
            )
        for group_label, group_df in starter_groups:
            render_canonical_section_header(
                f"{group_label} | {len(group_df)}",
                subtitle="Projected core group",
                heading_level=3,
            )
            render_player_scan_cards(
                group_df.sort_values(score_field, ascending=False),
                score_field=score_field,
                title=group_label,
                note="Projected core group",
                max_items=len(group_df),
                show_slot=True,
                status_label="Core",
                extra_tags_fn=lambda row: ["Core"] if _safe_text(row.get("role")) == "Core" else ["Projected"],
                note_fn=lambda row: canonical_player_ranking.format_compact_rank(
                    row.get("canonical_overall_rank", row.get("overall_rank")),
                    row.get("canonical_position_rank", row.get("position_rank")),
                    row.get("position"),
                    unavailable_reason=row.get("rank_unavailable_reason"),
                ),
                compact=True,
                enable_quick_view=True,
                quick_view_source_label=f"My Team - {group_label} Core",
                quick_view_key_prefix=f"my_team_{group_label.lower().replace(' ', '_')}_starters_{selected_league_id}_{my_roster_id}",
                show_header=False,
                design_system=True,
            )

    _canonical_header("Who Matters")
    if core_assets_df.empty:
        _render_empty_roster_section(
            "No core assets identified",
            "No player currently meets the existing core-asset criteria for this roster.",
        )
    else:
        render_canonical_section_header(
            "Core Assets",
            heading_level=3,
        )
        render_player_scan_cards(
            core_assets_df,
            score_field=score_field,
            title="Core Assets",
            note="Best current anchors under your current strategy focus.",
            max_items=min(len(core_assets_df), 6),
            status_label="Core Asset",
            extra_tags_fn=lambda row: ["Core"] if _safe_text(row.get("role")) == "Core" else [],
            note_fn=lambda row: canonical_player_ranking.format_compact_rank(
                row.get("canonical_overall_rank", row.get("overall_rank")),
                row.get("canonical_position_rank", row.get("position_rank")),
                row.get("position"),
                unavailable_reason=row.get("rank_unavailable_reason"),
            ),
            compact=True,
            enable_quick_view=True,
            quick_view_source_label="My Team - Core Assets",
            quick_view_key_prefix=f"my_team_core_assets_{selected_league_id}_{my_roster_id}",
            show_header=False,
            design_system=True,
        )

    position_items = _position_groups_items(
        team_needs_assessment,
        strengths=strengths,
        league_settings=league_settings,
    )
    _canonical_header("Position Groups")
    if not position_items:
        _render_empty_roster_section(
            "Position outlook unavailable",
            "Existing roster-needs assessments are not available for this roster yet.",
        )
    else:
        render_summary_tiles(
            workspace_ui.concept_items_as_summary_tiles(position_items),
            compact=True,
            key_prefix=f"my_team_position_groups_{selected_league_id}_{my_roster_id}",
        )

    if show_franchise_construction:
        _canonical_header("Draft Capital")
        capital_rows = compact_owned_draft_capital(draft_pick_assets, my_roster_id)
        st.markdown(
            _draft_capital_html(
                capital_rows,
                draft_capital_rank=team_row.get("draft_capital_rank") if hasattr(team_row, "get") else None,
                format_rank=format_rank,
            ),
            unsafe_allow_html=True,
        )

    _canonical_header("Depth")
    if key_backups_df.empty:
        _render_empty_roster_section(
            "No bench players",
            "No backup player is available in the current projected lineup.",
        )
    elif is_premium:
        with st.expander(f"Key backups | {len(key_backups_df)}", expanded=False):
            render_player_scan_cards(
                key_backups_df,
                score_field=score_field,
                title="Key Backups",
                note="First bench players who become meaningful if injuries or lineup changes hit.",
                max_items=min(len(key_backups_df), 6),
                status_label="Hold",
                extra_tags_fn=lambda row: ["Bench"] if _safe_text(row.get("role")) == "Bench" else [],
                note_fn=lambda row: canonical_player_ranking.format_compact_rank(
                    row.get("canonical_overall_rank", row.get("overall_rank")),
                    row.get("canonical_position_rank", row.get("position_rank")),
                    row.get("position"),
                    unavailable_reason=row.get("rank_unavailable_reason"),
                ),
                compact=True,
                enable_quick_view=True,
                quick_view_source_label="My Team - Key Backups",
                quick_view_key_prefix=f"my_team_key_backups_{selected_league_id}_{my_roster_id}",
                show_header=False,
                design_system=True,
            )
    elif render_premium_lock is not None:
        render_premium_lock(
            "Bench insulation detail",
            "See which backups matter if injuries hit — before your lineup becomes fragile.",
            feature="Premium My Team",
        )

    render_roster_utility_debug(
        my_roster_limit.get("lowest_utility_candidates"),
        title="Decision Debug: Bottom 15 roster utility candidates",
    )
    render_no_team_player_debug(
        my_roster_limit.get("rostered_no_team_players"),
        title="Decision Debug: Rostered No-Team / FA Players",
    )

    taxi_count = _safe_positive_int(my_roster_limit.get("taxi_count"), 0)
    reserve_count = _safe_positive_int(my_roster_limit.get("reserve_count"), 0)
    if taxi_count or reserve_count:
        bits = []
        if taxi_count:
            bits.append(f"Taxi {taxi_count}")
        if reserve_count:
            bits.append(f"IR {reserve_count}")
        st.caption(
            "Exempt roster slots: "
            + " · ".join(bits)
            + ". Individual Taxi/IR membership lists are not available on this route yet."
        )

    if advice_items:
        advice_markup = []
        for item in advice_items:
            primary = " advice-card-primary" if item.get("primary") else ""
            label = _safe_text(item.get("label")).strip().lower()
            tone = ""
            if item.get("primary") or label == "priority":
                tone = " advice-card-priority"
            elif label in {"need", "age"}:
                tone = " advice-card-need"
            elif label == "health":
                tone = " advice-card-health"
            elif label in {"depth", "leverage", "window"}:
                tone = " advice-card-opportunity"
            advice_markup.append(
                "<div class='advice-card dg-ui-card"
                + primary
                + tone
                + "'>"
                + f"<div class='advice-label'>{escape(_safe_text(item.get('label')))}</div>"
                + f"<div class='advice-title'>{escape(_safe_text(item.get('title')))}</div>"
                + f"<div class='advice-body'>{escape(_safe_text(item.get('body')))}</div>"
                + "</div>"
            )
        advice_html = workspace_ui.client_disclosure_html(
            "Front-office notes",
            "<div class='advice-grid'>" + "".join(advice_markup) + "</div>",
        )
        if advice_html:
            st.markdown(advice_html, unsafe_allow_html=True)
