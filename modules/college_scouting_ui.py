"""Streamlit presentation for College Scouting — the web equivalent of
mobile's CollegeProspectsScreen.tsx / ProspectScoutingDetailScreen.tsx.

Pure exposure of the already-built backend (modules.college_scouting +
services/mobile_api_service.py's ``/v1/scouting/*`` handlers): browse the
shared prospect catalog, submit/edit your own 1-5 grade + optional round
projection + optional note, see the pooled shared aggregate (average grade,
scout count, confidence), and manage a personal follow/unfollow watchlist.

No new valuation math lives here, and this module never fabricates a
prospect, grade, or confidence level — see modules/college_scouting.py's
"NO FABRICATED DATA" docstring section. An empty Supabase ``college_prospects``
table is the honest, expected state until real prospects are migrated in,
and renders the same empty state a real-but-temporarily-unreachable catalog
would.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, MutableMapping

import streamlit as st

from modules import account_store
from modules import auth_supabase
from modules import college_scouting
from modules import html_rendering
from modules import ui_primitives
from modules.player_cards import player_position_badge_html
from modules.trade_visual_language import TRADE_VISUAL_LANGUAGE_CSS, confidence_indicator_html

COLLEGE_SCOUTING_CSS = """
<style>
.dg-college-scouting-intro{color:var(--color-text-secondary);font:var(--font-body);margin-bottom:var(--space-md);max-width:48rem}
.dg-college-scouting-card{background:var(--surface-1);border:var(--border-width-default) solid var(--border-standard);border-radius:var(--radius-panel);margin-bottom:var(--space-sm);padding:var(--space-sm) var(--space-md)}
.dg-college-scouting-top{align-items:center;display:flex;gap:var(--space-sm)}
.dg-college-scouting-identity{display:flex;flex-direction:column;min-width:0}
.dg-college-scouting-name{color:var(--color-text-primary);font:var(--font-card-title)}
.dg-college-scouting-meta{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-college-scouting-aggregate-row{align-items:center;border-block-start:var(--border-width-default) solid var(--color-border);display:flex;gap:var(--space-sm);margin-top:var(--space-sm);padding-top:var(--space-sm)}
.dg-college-scouting-aggregate{color:var(--color-text-secondary);font:var(--font-card-title)}
.dg-college-scouting-my-grade{color:var(--color-accent);font:var(--type-supporting-metadata);margin-top:var(--space-2xs)}
</style>
"""


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _aggregate_text(aggregate: dict[str, Any]) -> str:
    avg_grade = aggregate.get("avg_grade")
    scout_count = int(aggregate.get("scout_count") or 0)
    if avg_grade is None or scout_count == 0:
        return "Not yet scouted"
    return f"{avg_grade:.1f} avg · {scout_count} {'scout' if scout_count == 1 else 'scouts'}"


def _prospect_card_html(row: dict[str, Any]) -> str:
    from html import escape

    position = _safe_text(row.get("position"))
    name = _safe_text(row.get("name"), "Prospect")
    school = _safe_text(row.get("school"))
    draft_year = row.get("draft_year")
    class_bits = school
    if draft_year:
        class_bits = f"{school} · {draft_year} class" if school else f"{draft_year} class"

    aggregate = row.get("aggregate") or {}
    scout_count = int(aggregate.get("scout_count") or 0)
    confidence_html = ""
    if scout_count > 0:
        confidence_label = college_scouting._confidence_label(scout_count)
        confidence_html = confidence_indicator_html(confidence_label)

    my_report = row.get("my_report")
    my_grade_html = ""
    if my_report and my_report.get("grade") is not None:
        my_grade_html = (
            "<div class='dg-college-scouting-my-grade'>"
            f"Your grade: {escape(str(my_report.get('grade')))}/{college_scouting.MAX_GRADE}"
            "</div>"
        )

    return (
        "<article class='dg-college-scouting-card'>"
        "<div class='dg-college-scouting-top'>"
        f"{player_position_badge_html(position)}"
        "<div class='dg-college-scouting-identity'>"
        f"<div class='dg-college-scouting-name'>{escape(name)}</div>"
        f"<div class='dg-college-scouting-meta'>{escape(class_bits)}</div>"
        "</div></div>"
        "<div class='dg-college-scouting-aggregate-row'>"
        f"{confidence_html}"
        f"<span class='dg-college-scouting-aggregate'>{escape(_aggregate_text(aggregate))}</span>"
        "</div>"
        f"{my_grade_html}"
        "</article>"
    )


def _toggle_watchlist(
    *, prospect_id: str, user_id: str, access_token: str, config: dict, currently_on: bool
) -> None:
    if currently_on:
        account_store.delete_rows(
            config,
            access_token,
            college_scouting.WATCHLIST_TABLE,
            query=f"user_id=eq.{user_id}&prospect_id=eq.{prospect_id}",
        )
    else:
        account_store.upsert_row(
            config,
            access_token,
            college_scouting.WATCHLIST_TABLE,
            {"user_id": user_id, "prospect_id": prospect_id},
            on_conflict="user_id,prospect_id",
        )


def _save_report(
    *,
    prospect_id: str,
    user_id: str,
    access_token: str,
    config: dict,
    grade_key: str,
    round_key: str,
    note_key: str,
    flash_key: str,
) -> None:
    grade = college_scouting.normalize_grade(st.session_state.get(grade_key))
    if grade is None:
        st.session_state[flash_key] = ("warning", "Choose a grade before saving.")
        return
    round_raw = st.session_state.get(round_key) or None
    round_projection = (
        college_scouting.normalize_round_projection(round_raw) if round_raw else None
    )
    note = _safe_text(st.session_state.get(note_key))[:280]

    payload: dict[str, Any] = {
        "user_id": user_id,
        "prospect_id": prospect_id,
        "grade": grade,
        "note": note,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if round_projection is not None:
        payload["round_projection"] = round_projection

    ok, _error = account_store.upsert_row(
        config,
        access_token,
        college_scouting.SCOUTING_REPORTS_TABLE,
        payload,
        on_conflict="user_id,prospect_id",
    )
    st.session_state[flash_key] = (
        ("success", "Saved — thanks for scouting.")
        if ok
        else ("error", "Could not save your grade. Try again in a moment.")
    )


def _remove_report(
    *,
    prospect_id: str,
    user_id: str,
    access_token: str,
    config: dict,
    grade_key: str,
    round_key: str,
    note_key: str,
    flash_key: str,
) -> None:
    ok, _error = account_store.delete_rows(
        config,
        access_token,
        college_scouting.SCOUTING_REPORTS_TABLE,
        query=f"user_id=eq.{user_id}&prospect_id=eq.{prospect_id}",
    )
    if ok:
        st.session_state[grade_key] = None
        st.session_state[round_key] = None
        st.session_state[note_key] = ""
        st.session_state[flash_key] = ("success", "Removed your report.")
    else:
        st.session_state[flash_key] = ("error", "Could not remove your grade. Try again in a moment.")


def _render_prospect(
    row: dict[str, Any], *, user_id: str, access_token: str, config: dict
) -> None:
    pid = _safe_text(row.get("id"))
    if not pid:
        return
    html_rendering.render_html_fragment(_prospect_card_html(row))

    on_watchlist = bool(row.get("on_watchlist"))
    st.button(
        "Unfollow" if on_watchlist else "Follow",
        key=f"college_scouting_watchlist_{pid}",
        use_container_width=False,
        type="secondary",
        on_click=_toggle_watchlist,
        kwargs={
            "prospect_id": pid,
            "user_id": user_id,
            "access_token": access_token,
            "config": config,
            "currently_on": on_watchlist,
        },
    )

    my_report = row.get("my_report") or {}
    has_report = bool(row.get("my_report"))
    grade_key = f"college_scouting_grade_{pid}"
    round_key = f"college_scouting_round_{pid}"
    note_key = f"college_scouting_note_{pid}"
    flash_key = f"college_scouting_flash_{pid}"

    flash = st.session_state.pop(flash_key, None)
    if flash:
        tone, message = flash
        getattr(st, tone, st.info)(message)

    label = f"Edit your grade — {_safe_text(row.get('name'), 'this prospect')}" if has_report else f"Scout {_safe_text(row.get('name'), 'this prospect')}"
    with st.expander(label, expanded=False):
        grade_options = list(range(college_scouting.MIN_GRADE, college_scouting.MAX_GRADE + 1))
        if grade_key not in st.session_state:
            st.session_state[grade_key] = my_report.get("grade")
        st.pills(
            "Overall grade (1 = pass, 5 = elite)",
            grade_options,
            selection_mode="single",
            key=grade_key,
        )

        round_options = [0] + list(
            range(college_scouting.MIN_ROUND_PROJECTION, college_scouting.MAX_ROUND_PROJECTION + 1)
        )
        if round_key not in st.session_state:
            st.session_state[round_key] = my_report.get("round_projection") or 0
        st.pills(
            "Round projection (optional)",
            round_options,
            selection_mode="single",
            format_func=lambda v: "No projection" if v == 0 else f"Round {v}",
            key=round_key,
        )

        if note_key not in st.session_state:
            st.session_state[note_key] = my_report.get("note") or ""
        st.text_area(
            "Note (optional)",
            key=note_key,
            max_chars=280,
            placeholder="What stands out on tape?",
        )

        st.button(
            "Update grade" if has_report else "Submit grade",
            key=f"college_scouting_save_{pid}",
            type="primary",
            on_click=_save_report,
            kwargs={
                "prospect_id": pid,
                "user_id": user_id,
                "access_token": access_token,
                "config": config,
                "grade_key": grade_key,
                "round_key": round_key,
                "note_key": note_key,
                "flash_key": flash_key,
            },
        )
        if has_report:
            st.button(
                "Remove my report",
                key=f"college_scouting_remove_{pid}",
                type="secondary",
                on_click=_remove_report,
                kwargs={
                    "prospect_id": pid,
                    "user_id": user_id,
                    "access_token": access_token,
                    "config": config,
                    "grade_key": grade_key,
                    "round_key": round_key,
                    "note_key": note_key,
                    "flash_key": flash_key,
                },
            )


def render_college_scouting_workspace(
    *,
    session: MutableMapping[str, Any],
    config: dict | None = None,
) -> None:
    """Browse the shared prospect catalog, scout, and manage a watchlist.

    Fails soft exactly like the mobile screen: a missing/unreachable
    ``college_prospects`` table is the honest "No prospects yet" empty
    state, never a fabricated row (modules.college_scouting's "NO
    FABRICATED DATA" policy).
    """

    html_rendering.inject_global_styles(COLLEGE_SCOUTING_CSS)
    html_rendering.inject_global_styles(f"<style>{TRADE_VISUAL_LANGUAGE_CSS}</style>")

    user_id = auth_supabase.current_user_id(session)
    access_token = auth_supabase.current_access_token(session)
    if not user_id or not access_token:
        ui_primitives.render_empty_state_panel(
            "Sign in to use College Scouting",
            "Submit a grade on a college prospect and it pools into one shared "
            "signal with every other scout.",
            kind="unavailable",
        )
        return

    resolved_config = config if config is not None else auth_supabase.get_supabase_config()

    html_rendering.render_html_fragment(
        "<p class='dg-college-scouting-intro'>Every signed-in user's grade on a "
        "prospect pools into one shared signal — that shared aggregate, not "
        "any single grade, can influence rookie draft-class strength. Your own "
        "grade and watchlist stay yours to edit any time.</p>"
    )

    prospects, prospects_error = college_scouting.get_cached_all_prospects(resolved_config, access_token)
    reports, _reports_error = college_scouting.get_cached_all_scouting_reports(resolved_config, access_token)
    watchlist_rows, _watchlist_error = account_store.fetch_rows(
        resolved_config, access_token, college_scouting.WATCHLIST_TABLE, user_id=user_id
    )
    watchlist_ids = {
        _safe_text(row.get("prospect_id")) for row in watchlist_rows if row.get("prospect_id")
    }

    rows = college_scouting.build_prospect_views(
        prospects, reports, my_user_id=user_id, watchlist_prospect_ids=watchlist_ids
    )

    if not rows:
        if prospects_error:
            ui_primitives.render_empty_state_panel(
                "College Scouting isn't connected yet",
                "The prospect catalog isn't reachable right now. Check back soon.",
                kind="unavailable",
            )
        else:
            ui_primitives.render_empty_state_panel(
                "No prospects yet",
                "Check back soon — the prospect pool is still growing.",
                kind="no-data",
            )
        return

    filter_choice = st.pills(
        "College Scouting view",
        ["All Prospects", "My Watchlist"],
        selection_mode="single",
        default="All Prospects",
        key="college_scouting_filter",
        label_visibility="collapsed",
    )
    visible = (
        [row for row in rows if row.get("on_watchlist")]
        if filter_choice == "My Watchlist"
        else rows
    )

    if not visible:
        ui_primitives.render_empty_state_panel(
            "No prospects followed yet",
            "Follow a prospect from All Prospects to track them here.",
            kind="filtered-empty",
        )
        return

    for row in visible:
        _render_prospect(row, user_id=user_id, access_token=access_token, config=resolved_config)
