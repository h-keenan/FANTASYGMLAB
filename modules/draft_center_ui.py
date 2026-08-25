from datetime import datetime
from html import escape
from typing import Callable

import pandas as pd
import streamlit as st

from modules import deferred_rendering
from modules import draft_assistant
from modules import league_workspace_ui
from modules import live_draft_ui
from modules import metric_graphic_primitives as mgp
from modules import team_eval as team_eval_module
from modules import workspace_ui


DRAFT_CENTER_PANES = (
    "Overview",
    "Current Draft",
    "History",
    "Scouting",
    "Watchlist",
)

_safe_text = league_workspace_ui._safe_text
_safe_float = league_workspace_ui._safe_float
_safe_positive_int = league_workspace_ui._safe_positive_int
_format_score = league_workspace_ui._format_score
_format_rank = league_workspace_ui._format_rank
tidy_label = league_workspace_ui.tidy_label
owner_handle = league_workspace_ui.owner_handle



def _available_card_board(available_pool: pd.DataFrame, score_field: str) -> pd.DataFrame:
    """Presentation adapter only: preserve the canonical Draft Center value and order."""
    if available_pool is None or available_pool.empty:
        return pd.DataFrame()
    board = available_pool.loc[:, ~available_pool.columns.duplicated(keep="last")].copy()
    effective_score = score_field if score_field in board.columns else "value_score"
    if effective_score not in board.columns:
        board[effective_score] = 0
    board["base_value"] = pd.to_numeric(board[effective_score], errors="coerce").fillna(0.0)
    board["league_adjusted_draft_score"] = board["base_value"]
    board = board.sort_values(effective_score, ascending=False, kind="stable").reset_index(drop=True)
    board["overall_rank"] = range(1, len(board) + 1)
    board["position_rank"] = board.groupby(
        board.get("position", pd.Series(dtype=str)).astype(str).str.upper()
    ).cumcount() + 1
    board["tier"] = board.get(
        "player_tier",
        board.get("tier", pd.Series("Board", index=board.index)),
    ).fillna("Board").astype(str)
    board["movement"] = 0
    board["recommendation_label"] = ""
    board["recommendation_reason"] = board.get(
        "opportunity_label",
        pd.Series("Canonical Draft Center ranking.", index=board.index),
    ).fillna("Canonical Draft Center ranking.").astype(str)
    return board


def _format_timestamp(timestamp: float | int | None) -> str:
    if not timestamp:
        return "Not refreshed yet"
    try:
        return datetime.fromtimestamp(float(timestamp)).strftime("%b %-d, %-I:%M %p")
    except ValueError:
        return datetime.fromtimestamp(float(timestamp)).strftime("%b %#d, %#I:%M %p")
    except Exception:
        return "Not refreshed yet"


def _draft_player_option_label(row: pd.Series, score_field: str, format_score: Callable) -> str:
    name = _safe_text(row.get("name"), "Player")
    position = _safe_text(row.get("position"), "Player").upper()
    team = _safe_text(row.get("team"), "FA").upper() or "FA"
    value = format_score(row.get(score_field, row.get("value_score", 0)))
    return f"{name} | {position} | {team} | {value}"


def _draft_assistant_status_note(context: dict, manual_count: int, last_refresh: float | int | None) -> str:
    mode = _safe_text(context.get("mode_label"), "Manual mode")
    status = _safe_text(context.get("draft_status_label"), "Unknown")
    picks_made = _safe_positive_int(context.get("picks_made"), 0)
    total_picks = _safe_positive_int(context.get("total_picks"), 0)
    total_text = f"{picks_made} of {total_picks}" if total_picks else str(picks_made)
    draft_count = _safe_positive_int(context.get("draft_count"), 0)
    selected_id = _safe_text(context.get("selected_draft_id"))
    selected_suffix = f" | Draft {selected_id[-6:]}" if selected_id else ""
    return (
        f"{mode} | {draft_count} draft{'s' if draft_count != 1 else ''} found | "
        f"{status}{selected_suffix} | {total_text} picks logged | "
        f"{manual_count} manual override{'s' if manual_count != 1 else ''} | "
        f"Last refreshed: {_format_timestamp(last_refresh)}"
    )


def _recommendation_row_html(
    item: dict,
    *,
    score_field: str,
    score_label: str,
    compact_player_row_html: Callable,
) -> str:
    player = item.get("player") or {}
    bucket = _safe_text(item.get("bucket"), "Draft pick")
    reason = _safe_text(item.get("reason"))
    row = pd.Series(player)
    return (
        "<div class='draft-assistant-bucket'>"
        f"<div class='draft-assistant-bucket-label'>{escape(bucket)}</div>"
        + compact_player_row_html(
            row,
            score_field=score_field,
            score_label=score_label,
            status_label=bucket,
            note_text=reason,
            extra_tags=[bucket],
            interactive=True,
        )
        + "</div>"
    )


def _pick_grade_tone(grade: str) -> str:
    grade = _safe_text(grade).upper()
    if grade.startswith("A"):
        return "strong"
    if grade.startswith("B"):
        return "solid"
    if grade.startswith("C"):
        return "watch"
    if grade in {"D", "F"}:
        return "risk"
    return "muted"


def _completed_pick_card_html(row: dict, *, score_label: str, format_score: Callable) -> str:
    pick_label = _safe_text(row.get("pick_label"), "Pick")
    player_name = _safe_text(row.get("player_name"), "Unknown player")
    position = _safe_text(row.get("position")).upper()
    team = _safe_text(row.get("team")).upper()
    meta = " | ".join(part for part in [position, team] if part) or "Unmatched"
    roster_id = _safe_positive_int(row.get("roster_id"), 0)
    roster_label = f"Roster {roster_id}" if roster_id else "Roster unknown"
    grade = _safe_text(row.get("grade"), "Ungraded")
    grade_reason = _safe_text(row.get("grade_reason"), "Grade unavailable.")
    matched = bool(row.get("matched"))
    value_text = format_score(row.get("value")) if matched else "N/A"
    chips = []
    if row.get("is_my_pick"):
        chips.append("<span class='draft-review-chip mine'>Mine</span>")
    if not matched:
        chips.append("<span class='draft-review-chip unmatched'>Unmatched</span>")
    chips_html = "".join(chips)
    return (
        "<div class='draft-review-pick-card'>"
        "<div class='draft-review-pick-top'>"
        f"<div class='draft-review-grade grade-{escape(_pick_grade_tone(grade))}'>{escape(grade)}</div>"
        f"<div class='draft-review-pick-slot'>{escape(pick_label)}</div>"
        f"<div class='draft-review-player-name'>{escape(player_name)}</div>"
        f"<div class='draft-review-value'>{escape(value_text)}</div>"
        "</div>"
        f"<div class='draft-review-meta'>{escape(meta)}"
        f"{' · ' + escape(roster_label) if roster_id else ''}"
        f"{' · ' + escape(score_label) if matched else ''}"
        f"{chips_html}</div>"
        f"<div class='draft-review-reason'>{escape(grade_reason)}</div>"
        "</div>"
    )


def _completed_round_summary(rows: list[dict]) -> str:
    if not rows:
        return "No picks logged."
    user_picks = sum(1 for row in rows if row.get("is_my_pick"))
    graded = [row for row in rows if _safe_text(row.get("grade")) != "Ungraded"]
    grade_order = {
        "A+": 11,
        "A": 10,
        "A-": 9,
        "B+": 8,
        "B": 7,
        "B-": 6,
        "C+": 5,
        "C": 4,
        "C-": 3,
        "D": 2,
        "F": 1,
    }
    best = max(graded, key=lambda row: grade_order.get(_safe_text(row.get("grade")), 0), default=None)
    lowest = min(graded, key=lambda row: grade_order.get(_safe_text(row.get("grade")), 99), default=None)
    parts = [f"{len(rows)} pick{'s' if len(rows) != 1 else ''}"]
    if user_picks:
        parts.append(f"{user_picks} yours")
    if best:
        parts.append(f"best {best.get('grade')} - {_safe_text(best.get('player_name'), 'player')}")
    if lowest and lowest is not best:
        parts.append(f"lowest {lowest.get('grade')} - {_safe_text(lowest.get('player_name'), 'player')}")
    return " | ".join(parts)


def _completed_round_cards_html(rows: list[dict], *, score_label: str, format_score: Callable) -> str:
    return "<div class='draft-review-round-grid'>" + "".join(
        _completed_pick_card_html(
            row,
            score_label=score_label,
            format_score=format_score,
        )
        for row in rows
    ) + "</div>"


def render_draft_assistant(
    *,
    league_id: str,
    username: str,
    my_roster_id,
    df_players: pd.DataFrame,
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame,
    league_settings: dict,
    score_field: str,
    score_label: str,
    compact_player_row_html: Callable,
    render_tappable_player_html: Callable,
    open_player_quick_view: Callable,
    format_score: Callable,
    surface_intent: str = "current",
) -> dict:
    intent = str(surface_intent or "current").strip().casefold()
    if intent == "history":
        workspace_ui.render_section_header(
            "Draft History",
            kicker="Completed drafts",
            note="Open a prior recorded Sleeper draft to review picks, grades, ownership, and results. Grading logic is unchanged.",
            compact=True,
        )
    else:
        workspace_ui.render_section_header(
            "Current Draft",
            kicker="Active or current-year review",
            note="Live assistant while a draft is in progress. Completed current-year drafts open in review mode.",
            compact=True,
        )
    if not league_id:
        st.info("Select a league to open the Draft Assistant.")
        return {"review_mode": False, "active_mode": False, "draft_status": "unknown"}
    if df_players is None or df_players.empty:
        st.info("Player rankings are not available yet.")
        return {"review_mode": False, "active_mode": False, "draft_status": "unknown"}

    selected_key = f"draft_assistant_selected_draft_{league_id}_{username or 'user'}"
    draft_options = draft_assistant.fetch_league_draft_options(league_id)
    if intent == "history":
        selected_key = f"draft_history_selected_draft_{league_id}_{username or 'user'}"
        draft_options = [
            option
            for option in draft_options
            if draft_assistant.is_completed_draft_status(option.get("status"))
        ]
        if not draft_options:
            st.info("No completed Sleeper drafts are recorded for this league yet.")
            return {"review_mode": True, "active_mode": False, "draft_status": "unknown"}
    option_map = {
        _safe_text(option.get("label"), option.get("draft_id")): _safe_text(option.get("draft_id"))
        for option in draft_options
        if _safe_text(option.get("draft_id"))
    }
    manual_label = "Manual board / no Sleeper draft"
    option_labels = list(option_map.keys()) or ([manual_label] if intent != "history" else [])
    if intent != "history" and manual_label not in option_labels:
        option_labels.append(manual_label)
    if not option_labels:
        st.info("No completed Sleeper drafts are recorded for this league yet.")
        return {"review_mode": True, "active_mode": False, "draft_status": "unknown"}
    current_id = _safe_text(st.session_state.get(selected_key))
    default_label = next(
        (label for label, draft_id in option_map.items() if draft_id == current_id),
        option_labels[0],
    )
    selected_label = st.selectbox(
        "Recorded draft" if intent == "history" else "Draft board",
        option_labels,
        index=option_labels.index(default_label) if default_label in option_labels else 0,
        key=f"{selected_key}_label",
        help=(
            "Choose a completed Sleeper draft from recorded history."
            if intent == "history"
            else "Choose a Sleeper draft when available. Manual mode is always available as a fallback."
        ),
    )
    selected_draft_id = "" if selected_label == manual_label else option_map.get(selected_label, "")
    st.session_state[selected_key] = selected_draft_id

    refresh_key = draft_assistant.refresh_timestamp_state_key(username, league_id, selected_draft_id)
    refresh_cols = st.columns([2, 3])
    with refresh_cols[0]:
        refresh_clicked = st.button(
            "Refresh Draft Board",
            key=f"draft_assistant_refresh_{league_id}_{selected_draft_id or 'manual'}",
            use_container_width=True,
        )
    if refresh_clicked:
        draft_assistant.clear_sleeper_draft_caches()
        st.session_state[refresh_key] = datetime.now().timestamp()

    context = draft_assistant.build_live_draft_context(
        league_id,
        username=username,
        my_roster_id=my_roster_id,
        selected_draft_id=selected_draft_id,
        refresh=False,
    )
    draft_player_pool = draft_assistant.apply_draft_pool_filter(df_players, context)
    match_analysis = draft_assistant.analyze_drafted_pick_matches(
        context.get("live_picks"),
        draft_player_pool,
    )
    manual_key = draft_assistant.manual_drafted_state_key(username, league_id, selected_draft_id)
    st.session_state.setdefault(manual_key, [])
    manual_ids = draft_assistant.normalize_manual_ids(st.session_state.get(manual_key))
    drafted_ids = draft_assistant.merge_drafted_ids(
        match_analysis.get("matched_ids"),
        manual_ids,
    )
    draft_pool_ids = (
        draft_player_pool[draft_assistant.player_id_column(draft_player_pool)].map(draft_assistant.normalize_player_id)
        if draft_assistant.player_id_column(draft_player_pool)
        else pd.Series(dtype="object")
    )
    live_excluded_count = len(set(match_analysis.get("matched_ids") or []).intersection(set(draft_pool_ids)))
    available_pool = draft_assistant.build_available_player_pool(
        draft_player_pool,
        drafted_ids,
        score_field=score_field,
    )
    draft_complete = not draft_assistant.should_render_active_draft_sections(context)

    with refresh_cols[1]:
        st.caption(
            _draft_assistant_status_note(
                context,
                len(manual_ids),
                st.session_state.get(refresh_key),
            )
        )

    workspace_ui.render_summary_tiles(
        [
            {
                "label": "Mode",
                "value": _safe_text(context.get("mode_label"), "Manual mode"),
                "note": _safe_text(context.get("selected_draft_label"), selected_label),
                "tone": "strategy",
            },
            {
                "label": "Draft Status",
                "value": _safe_text(context.get("draft_status_label"), "Unknown"),
                "note": (
                    f"{_safe_text(context.get('selected_draft_type'), 'type unknown')} | "
                    f"Season {context.get('selected_draft_season') or 'unknown'} | "
                    f"Current pick {context.get('current_pick') or '-'}"
                ),
                "tone": "power",
            },
            {
                "label": "Drafted",
                "value": str(len(drafted_ids)),
                "note": (
                    f"{len(context.get('live_picks') or [])} Sleeper picks fetched | "
                    f"{match_analysis.get('id_match_count', 0)} ID | "
                    f"{match_analysis.get('fallback_match_count', 0)} name | "
                    f"{match_analysis.get('unmatched_count', 0)} unmatched | "
                    f"{len(manual_ids)} manual"
                ),
                "tone": "franchise",
            },
            {
                "label": "Available",
                "value": str(len(available_pool)),
                "note": (
                    "Rookie-style pool inferred"
                    if len(draft_player_pool) < len(df_players)
                    else "Filtered from current player pool"
                ),
                "tone": "opportunity",
            },
            {
                "label": "Your Picks",
                "value": (
                    ", ".join(f"#{pick}" for pick in context.get("my_upcoming_picks") or [])
                    or "Not inferred"
                ),
                "note": (
                    f"Draft slot {context.get('my_draft_slot')}"
                    if context.get("my_draft_slot")
                    else "Manual fallback stays available"
                ),
                "tone": "strategy",
            },
        ],
        compact=True,
    )

    if not context.get("draft_available"):
        st.info("No Sleeper draft board is selected. Manual mode is active.")
    elif draft_complete:
        st.markdown(
            "<div class='app-degraded-state'>Review mode: this Sleeper draft is complete. Active recommendations, Who To Consider, and the normal Available Board are hidden for this draft.</div>",
            unsafe_allow_html=True,
        )

    if match_analysis.get("unmatched_picks"):
        with st.expander(
            f"Diagnostics: Unmatched Sleeper picks ({match_analysis.get('unmatched_count', 0)})",
            expanded=False,
        ):
            st.caption(
                "These Sleeper picks did not match the app player pool by ID or exact metadata name. "
                "They are not hidden unless you add a manual override."
            )
            st.dataframe(
                pd.DataFrame(match_analysis.get("unmatched_picks") or [])[
                    ["pick", "roster_id", "raw_player_id", "player_name", "reason"]
                ],
                width="stretch",
                hide_index=True,
            )

    manual_expander_label = "Manual overrides (optional)"
    with st.expander(manual_expander_label, expanded=False):
        st.caption("Use this when Sleeper data is unavailable or slightly behind. Manual marks only live in this browser session.")
        searchable_pool = available_pool.head(500).copy()
        search_text = st.text_input(
            "Search available player to mark drafted",
            key=f"draft_assistant_manual_search_{league_id}_{selected_draft_id or 'manual'}",
            placeholder="Player name",
            autocomplete="off",
        )
        if search_text.strip() and not searchable_pool.empty:
            searchable_pool = searchable_pool[
                searchable_pool["name"]
                .fillna("")
                .astype(str)
                .str.contains(search_text.strip(), case=False, na=False)
            ].copy()
        option_lookup = {
            _draft_player_option_label(row, score_field, format_score): _safe_text(row.get("player_id"))
            for _, row in searchable_pool.head(80).iterrows()
            if _safe_text(row.get("player_id"))
        }
        if option_lookup:
            selected_player_label = st.selectbox(
                "Player",
                list(option_lookup.keys()),
                key=f"draft_assistant_manual_player_{league_id}_{selected_draft_id or 'manual'}",
            )
            mark_cols = st.columns([1, 1])
            with mark_cols[0]:
                def _mark_drafted() -> None:
                    player_id = option_lookup.get(selected_player_label)
                    if player_id and player_id not in list(
                        st.session_state.get(manual_key, [])
                    ):
                        current = [
                            str(pid)
                            for pid in st.session_state.get(manual_key, [])
                            if str(pid)
                        ]
                        st.session_state[manual_key] = sorted(set(current + [player_id]))

                st.button(
                    "Mark Drafted",
                    key=f"draft_assistant_mark_{league_id}_{selected_draft_id or 'manual'}",
                    use_container_width=True,
                    on_click=_mark_drafted,
                )
            with mark_cols[1]:
                def _reset_marks() -> None:
                    st.session_state[manual_key] = []

                st.button(
                    "Reset Manual Marks",
                    key=f"draft_assistant_reset_{league_id}_{selected_draft_id or 'manual'}",
                    use_container_width=True,
                    on_click=_reset_marks,
                )
        else:
            st.caption("No matching available players under the current search.")
        if manual_ids:
            manual_rows = draft_player_pool[draft_player_pool["player_id"].astype(str).isin(manual_ids)].copy()
            st.markdown("**Manual marks**")
            for _, row in manual_rows.sort_values(score_field, ascending=False).iterrows():
                remove_cols = st.columns([4, 1])
                with remove_cols[0]:
                    st.caption(_draft_player_option_label(row, score_field, format_score))
                with remove_cols[1]:
                    player_id = _safe_text(row.get("player_id"))

                    def _remove_mark(pid: str = player_id) -> None:
                        st.session_state[manual_key] = [
                            item
                            for item in st.session_state.get(manual_key, [])
                            if str(item) != pid
                        ]

                    st.button(
                        "Remove",
                        key=f"draft_assistant_remove_{league_id}_{selected_draft_id or 'manual'}_{player_id}",
                        use_container_width=True,
                        on_click=_remove_mark,
                    )

    if draft_complete:
        workspace_ui.render_section_header(
            "Completed Draft Review",
            kicker="Recap",
            note=(
                "Review mode only. Use the round cards to audit picks, grades, and unmatched Sleeper players without active draft advice."
            ),
            compact=True,
        )
        st.caption(
            f"{_safe_text(context.get('selected_draft_label'), 'Selected draft')} | "
            f"{_safe_text(context.get('draft_status_label'), 'Complete')} | "
            f"{len(context.get('live_picks') or [])} picks logged | "
            f"{live_excluded_count} matched/excluded | "
            f"{match_analysis.get('unmatched_count', 0)} unmatched | "
            f"{len(manual_ids)} manual override{'s' if len(manual_ids) != 1 else ''}"
        )
        review_rows = draft_assistant.completed_pick_review_rows(
            context.get("live_picks"),
            draft_player_pool,
            score_field=score_field,
            my_roster_id=my_roster_id,
        )
        user_pick_count = sum(1 for row in review_rows if row.get("is_my_pick"))
        if user_pick_count:
            st.caption(f"Your picks in this draft: {user_pick_count}")
        if review_rows:
            round_groups: dict[int, list[dict]] = {}
            for row in review_rows:
                round_groups.setdefault(_safe_positive_int(row.get("round"), 0), []).append(row)
            # Only first round open by default — long drafts stay scannable.
            for round_no in sorted(round_groups):
                rows = round_groups[round_no]
                my_count = sum(1 for row in rows if row.get("is_my_pick"))
                summary = _completed_round_summary(rows)
                label = (
                    f"Round {round_no} · {len(rows)} picks"
                    + (f" · {my_count} yours" if my_count else "")
                    if round_no
                    else f"Unknown round · {len(rows)} picks"
                )
                with st.expander(label, expanded=round_no == 1):
                    if summary:
                        st.caption(summary)
                    st.markdown(
                        _completed_round_cards_html(
                            rows,
                            score_label=score_label,
                            format_score=format_score,
                        ),
                        unsafe_allow_html=True,
                    )
        else:
            st.info("No Sleeper picks are logged for this completed draft.")
        if not available_pool.empty:
            # Single disclosure level — avoid expander-inside-expander table nesting.
            with st.expander("Historical remaining pool", expanded=False):
                st.caption(
                    "Review-only list of players not matched as drafted in this completed Sleeper draft. "
                    "This is not an active draft board."
                )
                board_cols = [
                    column
                    for column in ["name", "position", "team", "age", score_field, "player_tier", "opportunity_label"]
                    if column in available_pool.columns
                ]
                rename_map = {
                    "name": "Player",
                    "position": "Pos",
                    "team": "Team",
                    "age": "Age",
                    score_field: score_label,
                    "player_tier": "Tier",
                    "opportunity_label": "Opportunity",
                }
                board_df = available_pool[board_cols].head(80).rename(columns=rename_map).reset_index(drop=True)
                st.dataframe(board_df, hide_index=True, use_container_width=True)
        return {
            "review_mode": True,
            "active_mode": False,
            "draft_status": context.get("draft_status"),
            "selected_draft_id": context.get("selected_draft_id"),
        }

    recommendations = draft_assistant.build_recommendation_buckets(
        available_pool,
        roster_df=roster_df,
        lineup_df=lineup_df,
        league_settings=league_settings,
        score_field=score_field,
    )
    if recommendations:
        workspace_ui.render_section_header(
            "Recommendation Buckets",
            kicker="Who To Consider",
            note="Active draft mode only. Buckets reuse current values and roster-room coverage; need can break ties, but it will not erase a major value gap.",
            compact=True,
        )
        recommendation_html = "<div class='draft-assistant-bucket-grid'>" + "".join(
            _recommendation_row_html(
                item,
                score_field=score_field,
                score_label=score_label,
                compact_player_row_html=compact_player_row_html,
            )
            for item in recommendations
        ) + "</div>"
        clicked_player_id = render_tappable_player_html(
            html=recommendation_html,
            key_prefix=f"draft_assistant_recommendations_{league_id}_{selected_draft_id or 'manual'}",
        )
        if clicked_player_id:
            open_player_quick_view(
                clicked_player_id,
                source_label="Draft Assistant",
                source_note="Draft Assistant recommendation bucket.",
            )
    else:
        st.info("No draft recommendation buckets are available yet.")

    workspace_ui.render_section_header(
        "Available Board",
        kicker="Remaining Pool",
        note="Active draft board for live or not-started drafts. Search and filter the remaining pool after live and manual exclusions.",
        compact=True,
    )
    filter_cols = st.columns([2, 1])
    with filter_cols[0]:
        board_search = st.text_input(
            "Search available board",
            key=f"draft_assistant_board_search_{league_id}_{selected_draft_id or 'manual'}",
            placeholder="Search player name",
            autocomplete="off",
        )
    with filter_cols[1]:
        position_filter = st.selectbox(
            "Position",
            ["All", "QB", "RB", "WR", "TE", "K"],
            key=f"draft_assistant_board_pos_{league_id}_{selected_draft_id or 'manual'}",
        )
    board_view = available_pool.copy()
    if board_search.strip() and not board_view.empty:
        board_view = board_view[
            board_view["name"]
            .fillna("")
            .astype(str)
            .str.contains(board_search.strip(), case=False, na=False)
        ].copy()
    if position_filter != "All" and not board_view.empty:
        board_view = board_view[
            board_view["position"].fillna("").astype(str).str.upper().eq(position_filter)
        ].copy()
    ranked_board = _available_card_board(available_pool, score_field)
    if board_search.strip() and not ranked_board.empty:
        ranked_board = ranked_board[
            ranked_board["name"].fillna("").astype(str).str.contains(
                board_search.strip(), case=False, na=False
            )
        ].copy()
    if position_filter != "All" and not ranked_board.empty:
        ranked_board = ranked_board[
            ranked_board["position"].fillna("").astype(str).str.upper().eq(position_filter)
        ].copy()
    if ranked_board.empty:
        st.info("No available players match the current filters.")
    else:
        st.markdown(live_draft_ui.ranking_card_styles_html(), unsafe_allow_html=True)
        board_html = "<div class='live-rank-list'>" + "".join(
            live_draft_ui._ranking_row_html(row)
            for row in ranked_board.head(80).to_dict("records")
        ) + "</div>"
        clicked_player_id = render_tappable_player_html(
            html=board_html,
            key_prefix=f"draft_assistant_ranked_board_{league_id}_{selected_draft_id or 'manual'}",
        )
        if clicked_player_id:
            open_player_quick_view(
                clicked_player_id,
                source_label="Draft Assistant",
                source_note="Available player ranking board.",
            )
    return {
        "review_mode": False,
        "active_mode": True,
        "draft_status": context.get("draft_status"),
        "selected_draft_id": context.get("selected_draft_id"),
    }


def _recommendation_reason_text(value: str, limit: int = 120) -> str:
    text = " ".join(_safe_text(value).split())
    return league_workspace_ui._truncate_text(text, limit) if text else ""


def _draft_rank_cutoffs(league_size: int) -> tuple[int, int]:
    top_cut = max(2, league_size // 3)
    bottom_cut = max(top_cut + 1, league_size - top_cut + 1)
    return top_cut, bottom_cut


def _draft_posture_profile(
    team_row: pd.Series | dict | None,
    league_size: int,
) -> dict:
    team = team_row if isinstance(team_row, (pd.Series, dict)) else {}
    strategy_key = team_eval_module.normalize_team_strategy(
        team.get("strategy") or team.get("mode") or team.get("strategy_key")
    )
    draft_rank = _safe_positive_int(
        team.get("draft_capital_rank"),
        league_size or 99,
    )
    future_rank = _safe_positive_int(
        team.get("future_draft_capital_rank"),
        draft_rank or league_size or 99,
    )
    power_rank = _safe_positive_int(
        team.get("power_rank"),
        league_size or 99,
    )
    first_rounders = _safe_positive_int(team.get("first_rounders"), 0)
    top_cut, bottom_cut = _draft_rank_cutoffs(max(league_size, 1))

    if strategy_key in {"contender", "fringe_contender"}:
        if draft_rank <= top_cut and future_rank <= top_cut:
            return {
                "label": "Aggressive Contender",
                "note": f"Contending build with top-tier draft leverage. {_safe_positive_int(team.get('first_rounders'), 0)} tracked first-rounders gives this roster room to spend for starters without emptying the cupboard.",
                "tone": "power",
            }
        if draft_rank >= bottom_cut and future_rank >= bottom_cut:
            return {
                "label": "Capital-Constrained Contender",
                "note": "Current strength is ahead of future flexibility. Any win-now move should protect remaining premium outs unless the starter upgrade is obvious.",
                "tone": "weakness",
            }
        return {
            "label": "Balanced Contender",
            "note": "Competitive roster with usable draft flexibility. This team can buy selectively, but each future pick has to produce a clear current-lineup payoff.",
            "tone": "strategy",
        }

    if strategy_key in {"rebuild", "tank"}:
        if draft_rank <= top_cut and future_rank <= top_cut:
            return {
                "label": "Pick-Rich Rebuilder",
                "note": f"Rebuild path already has strong pick insulation with {first_rounders} tracked first-rounders. The leverage here is patience, or using surplus capital to tier up instead of chasing points.",
                "tone": "opportunity",
            }
        if future_rank <= top_cut or first_rounders >= 2:
            return {
                "label": "Future-Focused Rebuilder",
                "note": "Future capital is the main leverage point. Preserving premium picks and moving short-window veterans for more insulation should shape draft decisions first.",
                "tone": "opportunity",
            }
        return {
            "label": "Capital-Light Rebuilder",
            "note": "The rebuild label is there, but the pick cushion is not. This roster should treat veterans and movable depth as the fastest path to more draft insulation.",
            "tone": "risk",
        }

    if draft_rank >= bottom_cut and future_rank >= bottom_cut:
        return {
            "label": "Capital-Constrained Pivot",
            "note": "This roster has not picked a final direction and also lacks strong draft insulation. Creating optionality matters more than spending future picks right now.",
            "tone": "risk",
        }

    if power_rank <= top_cut and draft_rank <= top_cut:
        return {
            "label": "Balanced Contender",
            "note": "The team is competitive enough to buy, but still has enough capital to stay flexible. Draft moves should be selective rather than all-in.",
            "tone": "strategy",
        }

    return {
        "label": "Middle-Tier Pivot Candidate",
        "note": "This roster sits between a push and a reset. Draft decisions should prioritize preserving optionality until the market offers a clear buy or sell lane.",
        "tone": "strategy",
    }


def _draft_workspace_team_lines(
    df: pd.DataFrame,
    *,
    limit: int = 3,
    include_strategy: bool = False,
    include_draft: bool = False,
    include_future: bool = False,
    include_implication: bool = False,
    classification: str = "",
) -> list[str]:
    if df is None or df.empty:
        return ["No clear team cluster is standing out yet."]

    def _classification_reason(row, mode: str, implication: str) -> str:
        strategy = _safe_text(
            row.get("strategy_display"),
            tidy_label(row.get("mode", "unknown")),
        )
        draft_rank = _format_rank(row.get("draft_capital_rank"))
        future_rank = _format_rank(row.get("future_draft_capital_rank"))
        power_rank = _format_rank(row.get("power_rank"))
        firsts = _safe_positive_int(row.get("first_rounders"), 0)

        if mode in {"pick_buyer", "buy_picks"}:
            if team_eval_module.normalize_team_strategy(
                row.get("strategy_key")
                or row.get("strategy")
                or row.get("mode")
            ) in {"rebuild", "tank"}:
                return f"{strategy} timeline, but draft rank {draft_rank} says this roster still needs more future capital."
            return f"Draft rank {draft_rank} leaves too little flexibility for a {strategy.lower()} build."
        if mode in {"pick_seller", "sell_picks"}:
            return f"Power rank {power_rank} gives this roster a real reason to spend picks for points now."
        if mode == "pivot":
            return "Middle-tier power and franchise ranks leave this roster needing optionality before it picks a direction."
        if mode == "pick_rich":
            return f"{firsts} first-rounder{'s' if firsts != 1 else ''} and future rank {future_rank} keep the board open."
        if mode == "pick_poor":
            return f"Draft rank {draft_rank} and future rank {future_rank} leave this roster with very little pick leverage."
        if mode == "move_veterans":
            return f"{strategy} posture plus an older roster base makes veteran-for-pick moves easier to justify."
        if mode == "spend_future":
            return f"Contender pressure plus future rank {future_rank} makes this one of the cleaner all-in teams."
        return implication

    items: list[str] = []
    for _, row in df.head(limit).iterrows():
        team_name = _safe_text(row.get("team_name"), "Team")
        details: list[str] = []
        if include_strategy:
            details.append(
                _safe_text(
                    row.get("strategy_display"),
                    tidy_label(row.get("mode", "unknown")),
                )
            )
        if include_draft:
            details.append(
                f"Draft {_format_rank(row.get('draft_capital_rank'))}"
            )
        if include_future:
            details.append(
                f"Future {_format_rank(row.get('future_draft_capital_rank'))}"
            )
        implication = (
            _recommendation_reason_text(
                _safe_text(row.get("manager_trade_implication")),
                92,
            )
            if include_implication
            else ""
        )
        rationale = _recommendation_reason_text(
            _classification_reason(row, classification, implication),
            112,
        )
        if rationale:
            details.append(rationale)
        items.append(
            team_name + (f" | {' | '.join(details)}" if details else "")
        )
    return items


def render_your_draft_posture(
    draft_workspace: pd.DataFrame,
    *,
    my_roster_id,
) -> None:
    workspace_ui.render_section_header(
        "Your Draft Posture",
        kicker="Start Here",
        note="Read your own capital, future flexibility, and team direction before scanning the rest of the league.",
    )
    if (
        draft_workspace is None
        or draft_workspace.empty
        or my_roster_id is None
    ):
        st.info("Select a league roster to evaluate your draft posture.")
        return

    selected_row = draft_workspace[
        draft_workspace["roster_id"].astype(str) == str(my_roster_id)
    ]
    if selected_row.empty:
        st.info("No draft-capital row is available for your roster yet.")
        return

    team_row = selected_row.iloc[0]
    posture = _draft_posture_profile(team_row, len(draft_workspace))
    workspace_ui.render_summary_tiles(
        [
            {
                "label": "Draft Posture",
                "value": posture["label"],
                "note": posture["note"],
                "tone": posture["tone"],
            },
            {
                "label": "Draft Capital Rank",
                "value": _format_rank(team_row.get("draft_capital_rank")),
                "note": f"{_format_score(team_row.get('draft_capital'))} total capital",
                "tone": "franchise",
            },
            {
                "label": "Future Capital Rank",
                "value": _format_rank(
                    team_row.get("future_draft_capital_rank")
                ),
                "note": f"{_format_score(team_row.get('future_draft_capital'))} beyond the current rookie draft",
                "tone": "opportunity",
            },
            {
                "label": "Current Strategy",
                "value": _safe_text(
                    team_row.get("strategy_display"),
                    team_eval_module.team_strategy_label(
                        team_row.get("mode")
                    ),
                ),
                "note": f"Power {_format_rank(team_row.get('power_rank'))} | Franchise {_format_rank(team_row.get('franchise_rank'))}",
                "tone": "strategy",
            },
        ]
    )
    workspace_ui.render_analysis_cards(
        [
            {
                "label": "Draft Read",
                "title": "What this means for your next move",
                "items": [
                    posture["note"],
                    f"{_safe_positive_int(team_row.get('first_rounders'), 0)} tracked first-rounders | {_safe_positive_int(team_row.get('pick_count'), 0)} total picks.",
                    _safe_text(team_row.get("manager_trade_implication"))
                    or "Use this posture as the draft lens before you open Trade Hub or My Team.",
                ],
                "tone": posture["tone"],
            }
        ]
    )


def build_draft_decision_cards(
    draft_workspace: pd.DataFrame,
) -> list[dict]:
    if draft_workspace is None or draft_workspace.empty:
        return []

    working = draft_workspace.copy()
    league_size = len(working)
    _draft_rank_cutoffs(league_size)
    midpoint = (league_size + 1) / 2.0
    middle_low = max(1, int(midpoint) - 1)
    middle_high = min(league_size, int(midpoint) + 1)

    for column, default in {
        "power_rank": league_size,
        "franchise_rank": league_size,
        "draft_capital_rank": league_size,
        "future_draft_capital_rank": league_size,
        "draft_capital": 0.0,
        "future_draft_capital": 0.0,
        "pick_count": 0.0,
        "first_rounders": 0.0,
    }.items():
        working[column] = pd.to_numeric(
            working.get(column),
            errors="coerce",
        ).fillna(default)

    working["strategy_key"] = working.apply(
        lambda row: team_eval_module.normalize_team_strategy(
            row.get("strategy")
            or row.get("mode")
            or row.get("strategy_key")
        ),
        axis=1,
    )
    working["pivot_distance"] = (
        (working["power_rank"] - midpoint).abs()
        + (working["franchise_rank"] - midpoint).abs()
        + ((working["draft_capital_rank"] - midpoint).abs() * 0.55)
    )

    pick_buyers = working[
        working["strategy_key"].isin({"rebuild", "tank", "retool"})
    ].sort_values(
        [
            "draft_capital_rank",
            "future_draft_capital_rank",
            "power_rank",
            "team_name",
        ],
        ascending=[False, False, False, True],
    ).head(3)
    if pick_buyers.empty:
        pick_buyers = working.sort_values(
            [
                "draft_capital_rank",
                "future_draft_capital_rank",
                "team_name",
            ],
            ascending=[False, False, True],
        ).head(3)

    pick_sellers = working[
        working["strategy_key"].isin({"contender", "fringe_contender"})
    ].sort_values(
        [
            "power_rank",
            "draft_capital_rank",
            "future_draft_capital_rank",
            "team_name",
        ],
        ascending=[True, True, True, True],
    ).head(3)
    if pick_sellers.empty:
        pick_sellers = working.sort_values(
            ["power_rank", "draft_capital_rank", "team_name"],
            ascending=[True, True, True],
        ).head(3)

    pivot_candidates = working[
        working["power_rank"].between(middle_low, middle_high)
        & working["franchise_rank"].between(middle_low, middle_high)
        & ~working["strategy_key"].isin({"contender", "rebuild", "tank"})
    ].sort_values(
        ["pivot_distance", "team_name"],
        ascending=[True, True],
    ).head(3)
    if pivot_candidates.empty:
        pivot_candidates = working[
            ~working["strategy_key"].isin(
                {"contender", "rebuild", "tank"}
            )
        ].sort_values(
            ["pivot_distance", "team_name"],
            ascending=[True, True],
        ).head(3)

    pick_rich = working.sort_values(
        [
            "draft_capital",
            "future_draft_capital",
            "first_rounders",
            "team_name",
        ],
        ascending=[False, False, False, True],
    ).head(3)
    pick_poor = working.sort_values(
        [
            "draft_capital",
            "future_draft_capital",
            "pick_count",
            "team_name",
        ],
        ascending=[True, True, True, True],
    ).head(3)

    return [
        {
            "label": "Best Pick Buyers",
            "title": "Teams that should be acquiring more picks",
            "tone": "opportunity",
            "items": _draft_workspace_team_lines(
                pick_buyers,
                include_strategy=True,
                include_draft=True,
                include_future=True,
                classification="pick_buyer",
            ),
        },
        {
            "label": "Best Pick Sellers",
            "title": "Teams best positioned to spend picks for points now",
            "tone": "power",
            "items": _draft_workspace_team_lines(
                pick_sellers,
                include_strategy=True,
                include_draft=True,
                include_future=True,
                classification="pick_seller",
            ),
        },
        {
            "label": "Pivot Candidates",
            "title": "Middle teams that still need a draft direction",
            "tone": "strategy",
            "items": _draft_workspace_team_lines(
                pivot_candidates,
                include_strategy=True,
                include_draft=True,
                include_future=True,
                classification="pivot",
            ),
        },
        {
            "label": "Pick-Rich Teams",
            "title": "The strongest future capital bases in the league",
            "tone": "strength",
            "items": _draft_workspace_team_lines(
                pick_rich,
                include_strategy=True,
                include_draft=True,
                include_future=True,
                classification="pick_rich",
            ),
        },
        {
            "label": "Pick-Poor Teams",
            "title": "The thinnest future cupboards right now",
            "tone": "weakness",
            "items": _draft_workspace_team_lines(
                pick_poor,
                include_strategy=True,
                include_draft=True,
                include_future=True,
                classification="pick_poor",
            ),
        },
    ]


def build_draft_partner_cards(
    draft_workspace: pd.DataFrame,
) -> list[dict]:
    if draft_workspace is None or draft_workspace.empty:
        return []

    working = draft_workspace.copy()
    league_size = len(working)
    top_cut, _ = _draft_rank_cutoffs(league_size)
    midpoint = (league_size + 1) / 2.0

    for column, default in {
        "power_rank": league_size,
        "franchise_rank": league_size,
        "draft_capital_rank": league_size,
        "future_draft_capital_rank": league_size,
        "age_rank": league_size,
    }.items():
        working[column] = pd.to_numeric(
            working.get(column),
            errors="coerce",
        ).fillna(default)

    working["strategy_key"] = working.apply(
        lambda row: team_eval_module.normalize_team_strategy(
            row.get("strategy")
            or row.get("mode")
            or row.get("strategy_key")
        ),
        axis=1,
    )

    likely_buy_picks = working[
        working["strategy_key"].isin({"rebuild", "tank", "retool"})
    ].sort_values(
        [
            "draft_capital_rank",
            "future_draft_capital_rank",
            "age_rank",
            "team_name",
        ],
        ascending=[False, False, False, True],
    ).head(3)

    likely_sell_picks = working[
        working["strategy_key"].isin({"contender", "fringe_contender"})
    ].sort_values(
        [
            "power_rank",
            "draft_capital_rank",
            "future_draft_capital_rank",
            "team_name",
        ],
        ascending=[True, True, True, True],
    ).head(3)

    likely_move_veterans = working[
        working["strategy_key"].isin({"rebuild", "tank", "retool"})
        & working["age_rank"].ge(midpoint)
    ].sort_values(
        ["age_rank", "power_rank", "draft_capital_rank", "team_name"],
        ascending=[False, False, False, True],
    ).head(3)
    if likely_move_veterans.empty:
        likely_move_veterans = working[
            working["strategy_key"].isin({"rebuild", "tank", "retool"})
        ].sort_values(
            ["power_rank", "age_rank", "team_name"],
            ascending=[False, False, True],
        ).head(3)

    likely_spend_future = working[
        working["strategy_key"].isin({"contender", "fringe_contender"})
        & working["future_draft_capital_rank"].le(max(top_cut, 3))
    ].sort_values(
        ["future_draft_capital_rank", "power_rank", "team_name"],
        ascending=[True, True, True],
    ).head(3)
    if likely_spend_future.empty:
        likely_spend_future = likely_sell_picks.head(3)

    return [
        {
            "label": "Likely To Buy Picks",
            "title": "Teams most likely to add future capital",
            "tone": "opportunity",
            "items": _draft_workspace_team_lines(
                likely_buy_picks,
                include_strategy=True,
                include_draft=True,
                include_implication=True,
                classification="buy_picks",
            ),
        },
        {
            "label": "Likely To Sell Picks",
            "title": "Teams most likely to move picks for current help",
            "tone": "power",
            "items": _draft_workspace_team_lines(
                likely_sell_picks,
                include_strategy=True,
                include_draft=True,
                include_implication=True,
                classification="sell_picks",
            ),
        },
        {
            "label": "Move Veterans For Picks",
            "title": "Teams most likely to trade short-window assets for future outs",
            "tone": "strategy",
            "items": _draft_workspace_team_lines(
                likely_move_veterans,
                include_strategy=True,
                include_future=True,
                include_implication=True,
                classification="move_veterans",
            ),
        },
        {
            "label": "Spend Future Capital",
            "title": "Teams with both the reason and the ammo to push now",
            "tone": "franchise",
            "items": _draft_workspace_team_lines(
                likely_spend_future,
                include_strategy=True,
                include_future=True,
                include_implication=True,
                classification="spend_future",
            ),
        },
    ]


def build_draft_summary_headline_tiles(
    *,
    draft_completed: bool,
    current_draft_year: int,
    draft_status: str,
    top_team,
    best_future,
    peak_capital: int,
    peak_future: int,
    pick_status_note: str = "",
) -> list[dict]:
    """Presentation payload for Draft Center headline tiles. Existing metrics only."""

    top_capital = int(top_team.get("draft_capital") or 0)
    top_picks = int(top_team.get("pick_count") or 0)
    future_capital = int(best_future.get("future_draft_capital") or 0)
    return [
        {
            "label": "Draft Status",
            "value": "Completed" if draft_completed else "Not Completed",
            "note": (
                f"{current_draft_year} rookie draft | "
                f"{_safe_text(draft_status, 'unknown')}"
            ),
            "tone": "power",
        },
        {
            "label": "Current-Year Pick Status",
            "value": "Inactive" if draft_completed else "Active",
            "note": _safe_text(pick_status_note),
            "tone": "strategy",
        },
        {
            "label": "Top Draft Capital Team",
            "value": _safe_text(top_team.get("team_name")),
            "note": f"{_format_score(top_team.get('draft_capital'))} total | {top_picks} picks",
            "tone": "franchise",
            "graphic": (
                mgp.leader_identity_html(rank=1)
                + mgp.capital_bar_html(value=top_capital, peak=peak_capital)
            ),
        },
        {
            "label": "Best Future Capital",
            "value": _safe_text(best_future.get("team_name")),
            "note": (
                f"{_format_score(best_future.get('future_draft_capital'))} "
                f"beyond {current_draft_year}"
            ),
            "tone": "opportunity",
            "graphic": (
                mgp.future_timeline_html(beyond_year=current_draft_year)
                + mgp.capital_bar_html(value=future_capital, peak=peak_future)
            ),
        },
    ]


def build_draft_summary_metric_tiles(
    *,
    owners: int,
    team_count: int,
    missing_count: int,
    missing_names: str,
    top_pick_team: str,
    top_pick_count: int,
    firsts: int,
    seconds: int,
    thirds: int | None,
    ownership_note: str,
) -> list[dict]:
    """Four-card Draft Capital scan graphics. Values stay in text."""

    return [
        {
            "label": "Tracked Pick Owners",
            "value": str(owners),
            "note": f"{team_count} teams",
            "badge_variant": "information",
            "graphic": mgp.coverage_strip_html(filled=owners, total=team_count),
        },
        {
            "label": "Teams Missing Key Picks",
            "value": str(missing_count),
            "note": missing_names if missing_names != "None" else "No major gaps",
            "badge_variant": "caution" if missing_count else "success",
            "graphic": mgp.gap_status_html(count=missing_count),
        },
        {
            "label": "Most Picks",
            "value": _safe_text(top_pick_team),
            "note": f"{int(top_pick_count or 0)} picks",
            "badge_variant": "opportunity",
            "graphic": (
                mgp.leader_identity_html(rank=1)
                + mgp.pick_stack_html(count=int(top_pick_count or 0))
            ),
        },
        {
            "label": "1st / 2nd Ownership",
            "value": f"{int(firsts)} / {int(seconds)}",
            "note": ownership_note,
            "badge_variant": "information",
            "graphic": mgp.round_podium_html(
                firsts=int(firsts),
                seconds=int(seconds),
                thirds=thirds,
            ),
        },
    ]


def build_draft_capital_dashboard_metric_tiles(
    *,
    most_name: str,
    most_capital: int,
    least_name: str,
    least_capital: int,
    peak_capital: int,
    no_first_count: int,
    no_first_names: str,
    hoarder_name: str,
    hoarder_picks: int,
    hoarder_names: str,
    lowest_name: str,
    lowest_note: str,
) -> list[dict]:
    """Sparse dashboard graphics: leader, comparison, gap. Not every card."""

    return [
        {
            "label": "Most Draft Capital",
            "value": _safe_text(most_name),
            "note": _format_score(most_capital),
            "badge_variant": "opportunity",
            "graphic": (
                mgp.leader_identity_html(rank=1)
                + mgp.capital_bar_html(value=int(most_capital or 0), peak=peak_capital)
            ),
        },
        {
            "label": "Least Draft Capital",
            "value": _safe_text(least_name),
            "note": _format_score(least_capital),
            "badge_variant": "caution",
            "graphic": mgp.capital_bar_html(
                value=int(least_capital or 0),
                peak=peak_capital,
            ),
        },
        {
            "label": "Teams With No 1sts",
            "value": str(no_first_count),
            "note": no_first_names or "None",
            "badge_variant": "caution" if no_first_count else "success",
            "graphic": mgp.gap_status_html(count=no_first_count),
        },
        {
            "label": "Pick Hoarders",
            "value": _safe_text(hoarder_name) if hoarder_name else "None",
            "note": (
                f"{int(hoarder_picks or 0)} picks" if hoarder_name else hoarder_names
            ),
            "badge_variant": "information",
            "graphic": (
                mgp.pick_stack_html(count=int(hoarder_picks or 0))
                if hoarder_name
                else ""
            ),
        },
        {
            "label": "Low Future Assets",
            "value": _safe_text(lowest_name),
            "note": lowest_note,
            "badge_variant": "caution",
        },
    ]


def render_draft_summary_section(
    draft_context: dict,
    draft_capital_summary: pd.DataFrame,
    draft_picks: list[dict],
    *,
    draft_year_columns: Callable,
):
    current_draft_year = (
        _safe_positive_int(
            draft_context.get("draft_year"),
            datetime.now().year,
        )
        or datetime.now().year
    )
    draft_completed = bool(draft_context.get("draft_completed"))
    pick_status = _safe_text(
        draft_context.get("current_year_pick_status"),
        "Current-year rookie picks are still active.",
    )
    if draft_capital_summary.empty:
        workspace_ui.render_section_header(
            "Draft Center",
            kicker="Rookie Draft Status",
            note=pick_status,
        )
        st.caption(_safe_text(draft_context.get("reason")))
        return

    summary = draft_capital_summary.copy()
    for column in [
        "draft_capital",
        "pick_count",
        "first_rounders",
        "second_rounders",
        "third_rounders",
    ]:
        summary[column] = (
            pd.to_numeric(summary.get(column), errors="coerce")
            .fillna(0)
            .astype(int)
        )
    year_cols = draft_year_columns(summary)
    current_year_col = f"pick_value_{current_draft_year}"
    future_year_cols = [
        column
        for column in year_cols
        if _safe_positive_int(
            str(column).replace("pick_value_", ""),
            0,
        )
        > current_draft_year
    ]
    summary["future_draft_capital"] = (
        summary[future_year_cols].sum(axis=1) if future_year_cols else 0
    )
    top_team = summary.sort_values(
        ["draft_capital", "pick_count"],
        ascending=[False, False],
    ).iloc[0]
    best_future = summary.sort_values(
        ["future_draft_capital", "first_rounders", "pick_count"],
        ascending=[False, False, False],
    ).iloc[0]
    missing_key = summary[
        (summary["first_rounders"] <= 0)
        | (summary["second_rounders"] <= 0)
    ].copy()
    missing_key = missing_key.sort_values(
        ["first_rounders", "second_rounders", "draft_capital"],
        ascending=[True, True, True],
    )
    no_current_first = 0
    no_current_second = 0
    if current_draft_year and any(
        int(pick.get("season") or 0) == current_draft_year
        for pick in draft_picks or []
    ):
        current_year_picks = pd.DataFrame(
            [
                pick
                for pick in draft_picks
                if int(pick.get("season") or 0) == current_draft_year
            ]
        )
        if not current_year_picks.empty:
            current_year_picks["round_num"] = (
                pd.to_numeric(
                    current_year_picks.get("round"),
                    errors="coerce",
                )
                .fillna(0)
                .astype(int)
            )
            owners = (
                pd.to_numeric(summary["roster_id"], errors="coerce")
                .fillna(0)
                .astype(int)
                .tolist()
            )
            no_current_first = int(
                current_year_picks[
                    current_year_picks["round_num"] == 1
                ]
                .groupby("owner_roster_id")
                .size()
                .reindex(owners, fill_value=0)
                .eq(0)
                .sum()
            )
            no_current_second = int(
                current_year_picks[
                    current_year_picks["round_num"] == 2
                ]
                .groupby("owner_roster_id")
                .size()
                .reindex(owners, fill_value=0)
                .eq(0)
                .sum()
            )

    workspace_ui.render_section_header(
        "Current draft status",
        kicker="Overview",
        note=pick_status,
    )
    peak_capital = int(summary["draft_capital"].max() or 0)
    peak_future = int(summary["future_draft_capital"].max() or 0)
    headline_tiles = build_draft_summary_headline_tiles(
        draft_completed=draft_completed,
        current_draft_year=current_draft_year,
        draft_status=_safe_text(draft_context.get("draft_status"), "unknown"),
        top_team=top_team,
        best_future=best_future,
        peak_capital=peak_capital,
        peak_future=peak_future,
        pick_status_note=_safe_text(draft_context.get("reason")),
    )
    workspace_ui.render_summary_tiles(headline_tiles)

    missing_names = (
        ", ".join(missing_key["team_name"].astype(str).head(4).tolist())
        if not missing_key.empty
        else "None"
    )
    top_pick_count = summary.sort_values(
        ["pick_count", "draft_capital"],
        ascending=[False, False],
    ).iloc[0]
    ownership_note = (
        f"{no_current_first} without current 1sts | {no_current_second} without current 2nds"
        if not draft_completed
        else "Current-year picks excluded after completed rookie draft"
    )
    from modules import executive_table_ui

    executive_table_ui.render_executive_metric_tiles(
        build_draft_summary_metric_tiles(
            owners=int(summary["pick_count"].gt(0).sum()),
            team_count=len(summary),
            missing_count=len(missing_key),
            missing_names=missing_names,
            top_pick_team=_safe_text(top_pick_count.get("team_name")),
            top_pick_count=int(top_pick_count.get("pick_count") or 0),
            firsts=int(summary["first_rounders"].sum()),
            seconds=int(summary["second_rounders"].sum()),
            thirds=int(summary["third_rounders"].sum()),
            ownership_note=ownership_note,
        )
    )

    ownership_display = summary[
        [
            column
            for column in [
                "draft_capital_rank",
                "team_name",
                "pick_count",
                "first_rounders",
                "second_rounders",
                "third_rounders",
                (
                    current_year_col
                    if current_year_col in summary.columns
                    else None
                ),
                *future_year_cols,
                "future_draft_capital",
            ]
            if column and column in summary.columns
        ]
    ].copy()
    rename_map = {
        "draft_capital_rank": "Rank",
        "team_name": "Team",
        "pick_count": "Picks",
        "first_rounders": "1sts",
        "second_rounders": "2nds",
        "third_rounders": "3rds",
        "future_draft_capital": "Future Capital",
    }
    if current_year_col in ownership_display.columns:
        rename_map[current_year_col] = f"{current_draft_year} Value"
    for column in future_year_cols:
        if column in ownership_display.columns:
            rename_map[column] = (
                f"{column.replace('pick_value_', '')} Value"
            )
    with st.expander("Detailed Table View", expanded=False):
        if deferred_rendering.render_section_gate(
            st,
            st.session_state,
            "draft_center_detailed_table",
            button_label="Load draft capital table",
            note="Capital cards stay first. Open the spreadsheet view only when you need every column.",
        ):
            st.dataframe(
                ownership_display.rename(columns=rename_map).reset_index(
                    drop=True
                ),
                width="stretch",
                hide_index=True,
            )


def render_draft_capital_dashboard(
    draft_capital_summary: pd.DataFrame,
    draft_picks: list[dict],
    *,
    draft_year_columns: Callable,
    render_draft_team_cards: Callable,
    team_tap_markup: Callable,
    render_team_card_tap_grid: Callable,
    open_league_team_from_tap: Callable,
    team_logo_html: Callable,
):
    if draft_capital_summary.empty:
        st.info("No draft-capital data is available for this league yet.")
        return

    summary = draft_capital_summary.copy()
    summary["draft_capital"] = (
        pd.to_numeric(summary["draft_capital"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    summary["pick_count"] = (
        pd.to_numeric(summary["pick_count"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    summary["first_rounders"] = (
        pd.to_numeric(summary["first_rounders"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    year_cols = draft_year_columns(summary)
    current_year = datetime.now().year
    future_year_cols = [
        column
        for column in year_cols
        if _safe_positive_int(
            str(column).replace("pick_value_", ""),
            0,
        )
        > current_year
    ]
    summary["future_draft_capital"] = (
        summary[future_year_cols].sum(axis=1) if future_year_cols else 0
    )
    summary = summary.sort_values(
        ["draft_capital_rank", "draft_capital", "team_name"],
        ascending=[True, False, True],
    )

    most = summary.iloc[0]
    least = summary.sort_values(
        ["draft_capital", "pick_count", "team_name"],
        ascending=[True, True, True],
    ).iloc[0]
    no_firsts = summary[summary["first_rounders"] <= 0]
    hoarders = summary.sort_values(
        ["pick_count", "first_rounders", "draft_capital"],
        ascending=[False, False, False],
    ).head(3)
    low_assets = summary.sort_values(
        ["draft_capital", "first_rounders", "pick_count"],
        ascending=[True, True, True],
    ).head(3)

    no_first_names = ", ".join(
        no_firsts["team_name"].astype(str).head(3).tolist()
    )
    if len(no_firsts) > 3:
        no_first_names += f" +{len(no_firsts) - 3}"
    hoarder_names = ", ".join(
        hoarders["team_name"].astype(str).head(2).tolist()
    )
    lowest = low_assets.iloc[0]
    zero_asset_count = int((summary["draft_capital"] <= 0).sum())
    from modules import executive_table_ui

    hoarder_row = hoarders.iloc[0] if not hoarders.empty else None
    executive_table_ui.render_executive_metric_tiles(
        build_draft_capital_dashboard_metric_tiles(
            most_name=_safe_text(most.get("team_name")),
            most_capital=int(most.get("draft_capital") or 0),
            least_name=_safe_text(least.get("team_name")),
            least_capital=int(least.get("draft_capital") or 0),
            peak_capital=int(summary["draft_capital"].max() or 0),
            no_first_count=len(no_firsts),
            no_first_names=no_first_names,
            hoarder_name=_safe_text(hoarder_row.get("team_name")) if hoarder_row is not None else "",
            hoarder_picks=int(hoarder_row.get("pick_count") or 0) if hoarder_row is not None else 0,
            hoarder_names=hoarder_names,
            lowest_name=_safe_text(lowest.get("team_name")),
            lowest_note=(
                f"{_format_score(lowest.get('draft_capital'))}"
                + (f" · {zero_asset_count} at zero" if zero_asset_count else "")
            ),
        )
    )

    render_draft_team_cards(
        summary,
        title="Capital Leaders",
        note="Best short scan for who controls the most draft leverage right now.",
        max_items=4,
        mode="top_capital",
    )
    render_draft_team_cards(
        summary,
        title="Future Concentration",
        note=f"Teams holding the strongest post-{current_year} capital base.",
        max_items=4,
        mode="future",
    )
    render_draft_team_cards(
        summary,
        title="Thin Draft Rooms",
        note="The weakest future-asset positions before you open the full pick list.",
        max_items=4,
        mode="thin",
    )

    board_rows = []
    for _, row in summary.iterrows():
        rank_value = int(
            pd.to_numeric(
                pd.Series([row.get("draft_capital_rank")]),
                errors="coerce",
            )
            .fillna(0)
            .iloc[0]
        )
        owner_text = owner_handle("", row.get("owner_name", "Owner"))
        tap_class, tap_attrs = team_tap_markup(row)
        board_rows.append(
            league_workspace_ui.ranked_leaderboard_row_html(
                rank_label=_format_rank(rank_value),
                team_name=_safe_text(row.get("team_name")),
                owner_text=owner_text,
                primary_metric=_format_score(row.get("draft_capital")),
                metric_label="Draft capital",
                interpretation=(
                    f"{int(row.get('first_rounders') or 0)} 1sts · "
                    f"{int(row.get('second_rounders') or 0)} 2nds"
                ),
                secondary=f"{int(row.get('pick_count') or 0)} future assets",
                logo_html=team_logo_html(
                    _safe_text(row.get("avatar_url")),
                    _safe_text(row.get("team_name")),
                    css_class="dg-ranked-logo",
                ),
                tap_class=tap_class,
                tap_attrs=tap_attrs,
                top_three=bool(rank_value and rank_value <= 3),
            )
        )
    clicked = render_team_card_tap_grid(
        html="<div class='dg-ranked-board'>" + "".join(board_rows) + "</div>",
        key_prefix="draft_capital_rankings",
    )
    if open_league_team_from_tap(clicked):
        st.rerun()
    st.caption(
        "Rank-first view up top. Raw draft-capital values stay in the detailed expander below."
    )

    display_cols = [
        "draft_capital_rank",
        "team_name",
        "owner_name",
        "draft_capital",
        "pick_count",
        "first_rounders",
        "second_rounders",
        "third_rounders",
    ] + year_cols
    rename_map = {
        "draft_capital_rank": "Rank",
        "team_name": "Team",
        "owner_name": "Owner",
        "draft_capital": "Total Draft Capital",
        "pick_count": "Picks",
        "first_rounders": "1sts",
        "second_rounders": "2nds",
        "third_rounders": "3rds",
    }
    rename_map.update(
        {
            column: f"{column.replace('pick_value_', '')} Value"
            for column in year_cols
        }
    )
    with st.expander("Detailed draft capital values", expanded=False):
        st.dataframe(
            summary[
                [
                    column
                    for column in display_cols
                    if column in summary.columns
                ]
            ]
            .rename(columns=rename_map)
            .reset_index(drop=True),
            width="stretch",
            hide_index=True,
        )


def render_team_pick_expanders(
    draft_capital_summary: pd.DataFrame,
    draft_picks: list[dict],
    *,
    safe_pick_value: Callable,
):
    if draft_capital_summary.empty:
        return

    picks_by_owner: dict[str, list[dict]] = {}
    for pick in draft_picks or []:
        owner_key = str(pick.get("owner_roster_id"))
        picks_by_owner.setdefault(owner_key, []).append(pick)

    for _, row in draft_capital_summary.sort_values(
        ["draft_capital_rank", "team_name"]
    ).iterrows():
        roster_key = str(row.get("roster_id"))
        team_name = _safe_text(
            row.get("team_name"),
            f"Team {roster_key}",
        )
        picks = sorted(
            picks_by_owner.get(roster_key, []),
            key=lambda pick: (
                _safe_positive_int(pick.get("season"), 9999),
                _safe_positive_int(pick.get("round"), 99),
                -safe_pick_value(pick),
            ),
        )
        expander_label = (
            f"#{int(row.get('draft_capital_rank') or 0)} {team_name} - "
            f"{_format_score(row.get('draft_capital'))} value, {int(row.get('pick_count') or 0)} picks"
        )
        with st.expander(expander_label, expanded=False):
            if not picks:
                st.caption("No tracked future picks for this roster.")
                continue
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Season": pick.get("season") or "",
                            "Round": pick.get("round") or "",
                            "Pick": pick.get("label", "Draft pick"),
                            "Tier": pick.get("pick_tier") or "",
                            "Projected Range": (
                                pick.get("projected_pick_range") or ""
                            ),
                            "Projection": (
                                f"E {round((_safe_float(pick.get('early_probability'), 0.0)) * 100):d}% | "
                                f"M {round((_safe_float(pick.get('mid_probability'), 0.0)) * 100):d}% | "
                                f"L {round((_safe_float(pick.get('late_probability'), 0.0)) * 100):d}%"
                            ),
                            "Value": safe_pick_value(pick),
                            "Original Team": (
                                pick.get("original_team_name") or ""
                            ),
                        }
                        for pick in picks
                    ]
                ),
                width="stretch",
                hide_index=True,
            )


def render_future_scouting_pane() -> None:
    """Product boundary for upcoming-class scouting — no fabricated prospects."""

    workspace_ui.render_section_header(
        "Future Draft Scouting",
        kicker="Upcoming class",
        note=(
            "Canonical prospect rankings are not connected. "
            "This surface will not invent players, schools, or boards."
        ),
        compact=True,
    )
    st.info(
        "No reliable canonical prospect feed is wired for future draft classes. "
        "The experimental static 2027 list in the repo stays dormant and is not shown here. "
        "Save real Sleeper players from Player Quick View onto GM Targets; "
        "those league-scoped saved assets appear on Watchlist."
    )


def render_draft_watchlist_pane(
    *,
    league_id: str,
    roster_id: str,
    df_players: pd.DataFrame,
    my_roster_player_ids,
    roster_player_map,
    roster_team_names,
    scoring_format: str,
    open_player_quick_view: Callable,
    open_destination: Callable,
    cached_headshot_data_url: Callable,
    render_premium_lock: Callable | None,
) -> None:
    """Reuse GM Targets as the user-scoped, league-safe draft watchlist owner."""

    from modules import gm_targets_ui

    workspace_ui.render_section_header(
        "Draft Watchlist",
        kicker="Saved assets",
        note=(
            "Watchlist is GM Targets for this league — not a second persistence store. "
            "Add or remove players from Player Quick View."
        ),
        compact=True,
    )
    gm_targets_ui.render_gm_targets_workspace(
        session=st.session_state,
        league_id=league_id,
        roster_id=str(roster_id or ""),
        df_players=df_players,
        my_roster_player_ids=my_roster_player_ids,
        roster_player_map=roster_player_map,
        roster_team_names=roster_team_names,
        scoring_format=scoring_format,
        open_player_quick_view=open_player_quick_view,
        open_destination=open_destination,
        cached_headshot_data_url=cached_headshot_data_url,
        render_premium_lock=render_premium_lock,
        title="",
    )


def render_draft_center_nav(*, league_id: str) -> str:
    """Return the selected Draft Center pane. Persists per league only."""

    key = f"draft_center_pane_{_safe_text(league_id) or 'none'}"
    selected = st.pills(
        "Draft Center sections",
        list(DRAFT_CENTER_PANES),
        default="Overview",
        key=key,
        label_visibility="collapsed",
    )
    return str(selected or "Overview")
