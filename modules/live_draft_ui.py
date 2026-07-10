"""Streamlit UI for the read-only Sleeper live draft assistant."""

from __future__ import annotations

from html import escape
from typing import Any, Callable

import pandas as pd
import streamlit as st

from modules import live_draft


def _text(value: Any, default: str = "") -> str:
    return live_draft.safe_text(value, default)


def _score(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "0.0"


def _draft_label(draft: dict[str, Any]) -> str:
    name = _text((draft.get("metadata") or {}).get("name") if isinstance(draft.get("metadata"), dict) else "", "")
    label = name or f"Draft {live_draft.safe_text(draft.get('draft_id'), 'Unknown')}"
    season = _text(draft.get("season"), "")
    status = live_draft.normalize_draft_status(draft.get("status")).replace("_", " ").title()
    return f"{label} | {season} | {status}".strip(" |")


def _draft_type(draft: dict[str, Any]) -> str:
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    settings = draft.get("settings") if isinstance(draft.get("settings"), dict) else {}
    parts = [
        _text(metadata.get("type") or draft.get("type"), "Draft").title(),
        _text(settings.get("type"), "").title(),
    ]
    return " / ".join(part for part in parts if part)


def _status_chip(text: str, tone: str = "neutral") -> str:
    return f"<span class='live-draft-chip live-draft-chip-{escape(tone)}'>{escape(text)}</span>"


def _render_draft_header(
    *,
    draft: dict[str, Any],
    state: dict[str, Any],
    selected_league_name: str,
    league_settings: dict[str, Any],
    score_label: str,
) -> None:
    qb_format = _text(league_settings.get("qb_format"), "1QB")
    scoring = _text(league_settings.get("scoring_format"), "PPR")
    league_format = _text(league_settings.get("league_format"), "Dynasty")
    status = live_draft.normalize_draft_status(draft.get("status"))
    status_tone = "success" if status == "drafting" else "warning" if status in {"paused", "pre_draft"} else "neutral"
    html = f"""
    <section class='live-draft-hero'>
        <div class='live-draft-kicker'>{escape(live_draft.LIVE_DRAFT_READ_ONLY_LABEL)}</div>
        <div class='live-draft-title'>Sleeper Live Draft</div>
        <div class='live-draft-copy'>{escape(selected_league_name or 'Active league')} draft room mirror. Draft timer is managed in Sleeper.</div>
        <div class='live-draft-chip-row'>
            {_status_chip(status.replace('_', ' ').title(), status_tone)}
            {_status_chip(f"{live_draft.safe_int(state.get('picks_made'), 0)} picks logged", "neutral")}
            {_status_chip(f"{live_draft.safe_int(state.get('rounds'), 0)} rounds", "neutral")}
            {_status_chip(f"{live_draft.safe_int(state.get('teams'), 0)} teams", "neutral")}
            {_status_chip(scoring, "neutral")}
            {_status_chip(qb_format, "neutral")}
            {_status_chip(league_format, "neutral")}
            {_status_chip(score_label, "neutral")}
        </div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def _render_on_clock(state: dict[str, Any]) -> None:
    is_mine = bool(state.get("is_my_pick"))
    tone = "mine" if is_mine else "waiting"
    picks_until = state.get("picks_until_mine")
    picks_until_label = (
        "On the clock"
        if is_mine
        else f"{picks_until} picks away"
        if picks_until is not None
        else "Slot unavailable"
    )
    html = f"""
    <section class='live-draft-command live-draft-command-{tone}'>
        <div>
            <div class='live-draft-kicker'>On The Clock</div>
            <div class='live-draft-command-title'>Pick {live_draft.safe_int(state.get('current_pick'), 0)}</div>
            <div class='live-draft-copy'>{escape(_text(state.get('current_team_name'), 'Unknown Team'))}</div>
        </div>
        <div class='live-draft-command-meta'>
            <div>{escape(picks_until_label)}</div>
            <div>Recent run: {escape(_text(state.get('positional_run'), 'No picks logged yet.'))}</div>
        </div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def _recommendation_html(rec: dict[str, Any]) -> str:
    meta = " · ".join(part for part in [_text(rec.get("position")), _text(rec.get("team"))] if part)
    return f"""
    <div class='live-draft-rec-card'>
        <div class='live-draft-rec-label'>{escape(_text(rec.get('label')))}</div>
        <div class='live-draft-rec-name'>{escape(_text(rec.get('name'), 'Player'))}</div>
        <div class='live-draft-rec-meta'>{escape(meta)} · Value {_score(rec.get('value'))} · {escape(_text(rec.get('tier'), 'Board Value'))}</div>
        <div class='live-draft-rec-reason'>{escape(_text(rec.get('reason')))}</div>
    </div>
    """


def _render_recommendations(state: dict[str, Any]) -> None:
    recs = state.get("recommendations") or []
    st.markdown(
        "<div class='live-draft-section-head'><span>Recommendations</span><small>Existing league-aware board, drafted players excluded.</small></div>",
        unsafe_allow_html=True,
    )
    if not recs:
        st.info("No recommendations are available yet. Load a league roster and draft board first.")
        return
    st.markdown("<div class='live-draft-rec-grid'>" + "".join(_recommendation_html(rec) for rec in recs) + "</div>", unsafe_allow_html=True)


def _pick_row_html(row: dict[str, Any], *, latest_pick_no: int) -> str:
    classes = ["live-draft-pick-row"]
    if row.get("is_mine"):
        classes.append("live-draft-pick-mine")
    if live_draft.safe_int(row.get("pick_no"), 0) == latest_pick_no:
        classes.append("live-draft-pick-latest")
    player_meta = " · ".join(part for part in [_text(row.get("position")), _text(row.get("team"))] if part)
    return f"""
    <div class='{" ".join(classes)}'>
        <div class='live-draft-pick-num'>#{live_draft.safe_int(row.get('pick_no'), 0)}</div>
        <div class='live-draft-pick-main'>
            <div class='live-draft-pick-player'>{escape(_text(row.get('player_name'), 'Unknown Player'))}</div>
            <div class='live-draft-pick-meta'>{escape(_text(row.get('round_pick')))} · {escape(player_meta or 'Metadata pending')}</div>
        </div>
        <div class='live-draft-pick-team'>{escape(_text(row.get('fantasy_team'), 'Unknown Team'))}</div>
    </div>
    """


def _render_pick_board(state: dict[str, Any]) -> None:
    rows = state.get("pick_rows") or []
    latest_pick_no = max((live_draft.safe_int(row.get("pick_no"), 0) for row in rows), default=0)
    st.markdown(
        "<div class='live-draft-section-head'><span>Draft Board</span><small>Latest pick and your picks are highlighted.</small></div>",
        unsafe_allow_html=True,
    )
    if not rows:
        st.info("No picks have been logged yet. This board will fill as Sleeper reports selections.")
        return
    st.markdown(
        "<div class='live-draft-board'>" + "".join(_pick_row_html(row, latest_pick_no=latest_pick_no) for row in rows[-36:]) + "</div>",
        unsafe_allow_html=True,
    )
    with st.expander("Full draft board", expanded=False):
        st.dataframe(pd.DataFrame(rows).drop(columns=["raw"], errors="ignore"), width="stretch", hide_index=True)


def _render_available_pool(
    state: dict[str, Any],
    *,
    score_field: str,
    score_label: str,
) -> None:
    pool = state.get("available_pool")
    st.markdown(
        "<div class='live-draft-section-head'><span>Available Player Pool</span><small>Drafted players are removed immediately.</small></div>",
        unsafe_allow_html=True,
    )
    if pool is None or pool.empty:
        st.info("No available players are loaded yet.")
        return
    col_filter, col_search = st.columns([1, 2])
    with col_filter:
        pos = st.selectbox("Filter", ["All", "QB", "RB", "WR", "TE", "Rookies", "Veterans"], key="live_draft_position_filter")
    with col_search:
        query = st.text_input("Search", key="live_draft_player_search", placeholder="Search available players")
    display = pool.copy()
    if pos in {"QB", "RB", "WR", "TE"} and "position" in display.columns:
        display = display[display["position"].astype(str).str.upper() == pos]
    elif pos == "Rookies" and "age" in display.columns:
        display = display[pd.to_numeric(display["age"], errors="coerce").fillna(99) <= 23]
    elif pos == "Veterans" and "age" in display.columns:
        display = display[pd.to_numeric(display["age"], errors="coerce").fillna(0) >= 24]
    if query and "name" in display.columns:
        display = display[display["name"].astype(str).str.contains(query, case=False, na=False)]
    cols = [column for column in ["name", "position", "team", "age", score_field, "player_tier", "opportunity_label"] if column in display.columns]
    table = display[cols].head(50).copy()
    if score_field in table.columns:
        table = table.rename(columns={score_field: score_label})
    table = table.rename(columns={"name": "Player", "position": "Pos", "team": "Team", "age": "Age", "player_tier": "Tier", "opportunity_label": "Context"})
    st.dataframe(table, width="stretch", hide_index=True)


def _render_team_boards(state: dict[str, Any]) -> None:
    rows = state.get("pick_rows") or []
    with st.expander("Recent picks, your picks, and positional run", expanded=False):
        if not rows:
            st.caption("No pick history is available yet.")
            return
        my_rows = [row for row in rows if row.get("is_mine")]
        st.caption(f"Recent positional run: {_text(state.get('positional_run'))}")
        st.dataframe(pd.DataFrame(rows[-12:]).drop(columns=["raw"], errors="ignore"), width="stretch", hide_index=True)
        if my_rows:
            st.markdown("**Your selections**")
            st.dataframe(pd.DataFrame(my_rows).drop(columns=["raw"], errors="ignore"), width="stretch", hide_index=True)
        def summarize_positions(positions: pd.Series) -> str:
            counts = positions.astype(str).value_counts()
            return " | ".join(f"{pos} {count}" for pos, count in counts.items())

        by_team = (
            pd.DataFrame(rows)
            .groupby("fantasy_team")["position"]
            .apply(summarize_positions)
            .reset_index(name="Positions")
            if rows
            else pd.DataFrame()
        )
        if not by_team.empty:
            st.markdown("**Picks by team**")
            st.dataframe(by_team, width="stretch", hide_index=True)


def render_live_draft_page(
    *,
    selected_league_id: str,
    selected_league_name: str,
    username: str,
    my_roster_id: Any,
    df_players: pd.DataFrame,
    roster_df: pd.DataFrame,
    rosters: list[dict[str, Any]],
    roster_profiles: dict[str, dict[str, Any]],
    league_settings: dict[str, Any],
    score_field: str,
    score_label: str,
    fetch_league_drafts: Callable[[str], list[dict[str, Any]]],
    fetch_draft: Callable[[str], dict[str, Any]],
    fetch_draft_picks: Callable[[str], tuple[list[dict[str, Any]], str]] = live_draft.fetch_sleeper_draft_picks,
    poll_interval_seconds: int = live_draft.LIVE_DRAFT_POLL_INTERVAL_SECONDS,
) -> None:
    st.markdown("<div class='live-draft-route-marker'></div>", unsafe_allow_html=True)
    if not selected_league_id:
        st.info("Load a Sleeper league to open the read-only live draft assistant.")
        return
    discovery = live_draft.discover_live_drafts(
        selected_league_id,
        fetch_league_drafts=fetch_league_drafts,
        fetch_draft=fetch_draft,
    )
    drafts = discovery.get("drafts") or []
    if discovery.get("error"):
        st.warning("Sleeper draft data could not be reached. Try Refresh Draft in a moment.")
    if not drafts:
        st.info("No Sleeper drafts were found for this league yet.")
        return

    labels = [_draft_label(draft) for draft in drafts]
    default_index = 0
    selected_label = st.selectbox("Draft", labels, index=default_index, key=f"live_draft_selector_{selected_league_id}")
    selected_draft = drafts[labels.index(selected_label)]
    draft_id = _text(selected_draft.get("draft_id"))
    if st.button("Refresh Draft", key=f"live_draft_refresh_{draft_id}", use_container_width=True):
        st.rerun()

    def render_snapshot() -> None:
        picks, pick_error = fetch_draft_picks(draft_id)
        draft_detail = fetch_draft(draft_id) or selected_draft
        draft_detail = {**selected_draft, **draft_detail, "draft_id": draft_id}
        state = live_draft.build_live_draft_state(
            draft=draft_detail,
            picks=picks,
            df_players=df_players,
            roster_df=roster_df,
            roster_profiles=roster_profiles,
            rosters=rosters,
            my_roster_id=my_roster_id,
            league_settings=league_settings,
            score_field=score_field,
        )
        _render_draft_header(
            draft=draft_detail,
            state=state,
            selected_league_name=selected_league_name,
            league_settings=league_settings,
            score_label=score_label,
        )
        st.caption(f"Last updated: {state.get('last_updated')} | Poll interval: {poll_interval_seconds}s")
        if pick_error:
            st.warning("Sleeper pick data is temporarily unavailable. The assistant is in degraded read-only mode.")
        if state.get("status") == "complete":
            st.success("Draft complete. Live polling is paused.")
        _render_on_clock(state)
        _render_recommendations(state)
        _render_pick_board(state)
        _render_available_pool(state, score_field=score_field, score_label=score_label)
        _render_team_boards(state)

    if hasattr(st, "fragment") and live_draft.normalize_draft_status(selected_draft.get("status")) != "complete":
        @st.fragment(run_every=f"{poll_interval_seconds}s")
        def live_draft_fragment():
            render_snapshot()

        live_draft_fragment()
    else:
        render_snapshot()
