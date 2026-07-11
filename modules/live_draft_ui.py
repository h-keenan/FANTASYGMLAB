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


def _movement_label(value: Any) -> str:
    movement = live_draft.safe_int(value, 0)
    if movement >= 2:
        return f"↑ {movement}"
    if movement <= -2:
        return f"↓ {abs(movement)}"
    return "—"


def _ranking_row_html(row: dict[str, Any]) -> str:
    rank = live_draft.safe_int(row.get("overall_rank"), 0)
    pos = _text(row.get("position"), "UNK").upper()
    pos_rank = live_draft.safe_int(row.get("position_rank"), 0)
    label = _text(row.get("recommendation_label"))
    label_html = f"<span class='live-rank-label'>{escape(label)}</span>" if label else ""
    movement = _movement_label(row.get("movement"))
    movement_html = f"<span class='live-rank-move'>{escape(movement)}</span>" if movement != "—" else ""
    meta = " · ".join(
        part for part in [
            pos,
            _text(row.get("team")),
            f"Age {live_draft.safe_int(row.get('age'), 0)}" if live_draft.safe_int(row.get("age"), 0) else "",
        ] if part
    )
    return f"""
    <article class='live-rank-row'>
        <div class='live-rank-number'>#{rank}</div>
        <div class='live-rank-main'>
            <div class='live-rank-topline'>
                <span class='live-rank-name'>{escape(_text(row.get('name'), 'Player'))}</span>
                {label_html}{movement_html}
            </div>
            <div class='live-rank-meta'>{escape(meta)} · {escape(_text(row.get('tier'), 'Depth'))} · {pos} #{pos_rank}</div>
            <div class='live-rank-reason'>{escape(_text(row.get('recommendation_reason')))}</div>
        </div>
        <div class='live-rank-score'>
            <strong>{_score(row.get('league_adjusted_draft_score'))}</strong>
            <small>Value {_score(row.get('base_value'))}</small>
        </div>
    </article>
    """


def _render_live_rankings(
    state: dict[str, Any],
    *,
    score_label: str,
) -> None:
    board = state.get("rankings")
    st.markdown(
        """
        <style>
        .live-rank-list{display:grid;gap:.42rem;margin:.45rem 0 1rem}
        .live-rank-row{align-items:center;background:linear-gradient(180deg,rgba(15,23,42,.96),rgba(8,13,24,.96));border:1px solid rgba(148,163,184,.16);border-radius:14px;display:grid;gap:.65rem;grid-template-columns:2.6rem minmax(0,1fr) auto;padding:.68rem .72rem}
        .live-rank-number{color:#7dd3fc;font-size:1rem;font-weight:950;text-align:center}
        .live-rank-main{min-width:0}.live-rank-topline{align-items:center;display:flex;flex-wrap:wrap;gap:.35rem}
        .live-rank-name{color:#f8fafc;font-size:.94rem;font-weight:900}.live-rank-label{background:rgba(56,189,248,.12);border:1px solid rgba(56,189,248,.28);border-radius:999px;color:#bae6fd;font-size:.58rem;font-weight:900;padding:.18rem .38rem;text-transform:uppercase}
        .live-rank-move{color:#86efac;font-size:.68rem;font-weight:900}.live-rank-meta,.live-rank-reason{color:#94a3b8;font-size:.72rem;line-height:1.28;margin-top:.15rem}.live-rank-reason{color:#cbd5e1}
        .live-rank-score{text-align:right}.live-rank-score strong{color:#f8fafc;display:block;font-size:.9rem}.live-rank-score small{color:#94a3b8;display:block;font-size:.6rem;white-space:nowrap}
        @media(max-width:640px){.live-rank-row{gap:.48rem;grid-template-columns:2.15rem minmax(0,1fr) auto;padding:.58rem .5rem}.live-rank-number{font-size:.88rem}.live-rank-name{font-size:.86rem}.live-rank-reason{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.live-rank-score strong{font-size:.82rem}}
        </style>
        <div class='live-draft-section-head'><span>Live Draft Rankings</span><small>Every available player, reranked for this league and roster.</small></div>
        """,
        unsafe_allow_html=True,
    )
    if board is None or board.empty:
        st.info("No available players are loaded yet.")
        return
    filter_options = ["Overall", "QB", "RB", "WR", "TE", "Rookies"]
    if (~board.get("is_rookie", pd.Series(False, index=board.index)).astype(bool)).any():
        filter_options.append("Veterans")
    selection = st.selectbox("Rankings", filter_options, key="live_draft_rank_filter")
    display = board
    if selection in {"QB", "RB", "WR", "TE"}:
        display = display[display["position"].astype(str).str.upper() == selection]
    elif selection == "Rookies":
        display = display[display["is_rookie"].astype(bool)]
    elif selection == "Veterans":
        display = display[~display["is_rookie"].astype(bool)]
    st.markdown(
        "<div class='live-rank-list'>" + "".join(_ranking_row_html(row) for row in display.to_dict("records")) + "</div>",
        unsafe_allow_html=True,
    )
    with st.expander("How the live score is built", expanded=False):
        st.caption(
            f"{score_label} remains the strongest input. Format, scarcity, roster fit, age/strategy, "
            "and likely availability until your next pick make modest adjustments; displayed scores are rounded."
        )
        detail_columns = [
            "overall_rank", "name", "base_value", "format_adjustment", "scarcity_score",
            "roster_fit_score", "age_strategy_adjustment", "availability_adjustment",
            "league_adjusted_draft_score",
        ]
        st.dataframe(display[[col for col in detail_columns if col in display.columns]].head(25), width="stretch", hide_index=True)
    player_options = {
        f"#{live_draft.safe_int(row.get('overall_rank'), 0)} {_text(row.get('name'), 'Player')}": row
        for row in display.head(75).to_dict("records")
    }
    if player_options:
        selected = st.selectbox("Player Quick View", list(player_options), key="live_draft_quick_view")
        row = player_options[selected]
        with st.expander(f"Quick View · {_text(row.get('name'), 'Player')}", expanded=False):
            st.caption(
                f"Overall #{live_draft.safe_int(row.get('overall_rank'), 0)} · "
                f"{_text(row.get('position')).upper()} #{live_draft.safe_int(row.get('position_rank'), 0)} · "
                f"{_text(row.get('tier'))}"
            )
            st.write(_text(row.get("recommendation_reason")))
            st.caption(
                f"Base {_score(row.get('base_value'))} | Format {_score(row.get('format_adjustment'))} | "
                f"Scarcity {_score(row.get('scarcity_score'))} | Fit {_score(row.get('roster_fit_score'))} | "
                f"Age/strategy {_score(row.get('age_strategy_adjustment'))} | Availability {_score(row.get('availability_adjustment'))}"
            )
            if st.button("Open in Trade Hub", key=f"live_rank_trade_{_text(row.get('player_id'))}", use_container_width=True):
                st.session_state["trade_hub_player_id"] = _text(row.get("player_id"))
                st.session_state["current_page"] = "trade_hub"
                st.rerun()

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
        picks_key = f"live_draft_last_picks_{draft_id}"
        ranks_key = f"live_draft_previous_ranks_{draft_id}"
        if pick_error:
            picks = st.session_state.get(picks_key, picks)
        else:
            st.session_state[picks_key] = picks
        previous_ranks = st.session_state.get(ranks_key, {})
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
            previous_ranks=previous_ranks,
        )
        rankings = state.get("rankings")
        if rankings is not None and not rankings.empty and not pick_error:
            st.session_state[ranks_key] = {
                _text(row.get("player_id")): live_draft.safe_int(row.get("overall_rank"), 0)
                for row in rankings.to_dict("records") if _text(row.get("player_id"))
            }
        _render_draft_header(
            draft=draft_detail,
            state=state,
            selected_league_name=selected_league_name,
            league_settings=league_settings,
            score_label=score_label,
        )
        st.caption(f"Last updated: {state.get('last_updated')} | Poll interval: {poll_interval_seconds}s")
        if pick_error:
            st.warning("Sleeper pick data is temporarily unavailable. Showing the last valid read-only rankings board.")
        if state.get("status") == "complete":
            st.success("Draft complete. Live polling is paused.")
        _render_on_clock(state)
        _render_live_rankings(state, score_label=score_label)
        _render_recommendations(state)
        _render_pick_board(state)
        _render_team_boards(state)

    if hasattr(st, "fragment") and live_draft.normalize_draft_status(selected_draft.get("status")) != "complete":
        @st.fragment(run_every=f"{poll_interval_seconds}s")
        def live_draft_fragment():
            render_snapshot()

        live_draft_fragment()
    else:
        render_snapshot()
