"""Streamlit UI for the read-only Sleeper live draft assistant."""

from __future__ import annotations

from html import escape
from typing import Any, Callable
import time

import pandas as pd
import streamlit as st

from modules import executive_table_ui
from modules import live_draft
from modules import performance
from modules import football_assets


def _text(value: Any, default: str = "") -> str:
    return live_draft.safe_text(value, default)


def _concise_reason(value: Any, limit: int = 145) -> str:
    text = " ".join(_text(value).split())
    if len(text) <= limit:
        return text
    sentence_end = max(text.rfind(". ", 0, limit), text.rfind("! ", 0, limit), text.rfind("? ", 0, limit))
    if sentence_end >= 55:
        return text[: sentence_end + 1]
    return text[: max(limit - 1, 0)].rstrip(" ,;:-") + "…"


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
    upcoming = state.get("my_upcoming_picks") or []
    upcoming_label = ", ".join(f"#{pick}" for pick in upcoming) or "Unavailable"
    html = f"""
    <section class='live-draft-command live-draft-command-{tone}'>
        <div>
            <div class='live-draft-kicker'>On The Clock</div>
            <div class='live-draft-command-title'>Pick {live_draft.safe_int(state.get('current_pick'), 0)} · Round {live_draft.safe_int(state.get('current_round'), 0)}</div>
            <div class='live-draft-copy'>{escape(_text(state.get('current_manager_name'), 'Unknown manager'))} · {escape(_text(state.get('current_team_name'), 'Unknown Team'))}</div>
        </div>
        <div class='live-draft-command-meta'>
            <div>{escape(picks_until_label)}</div>
            <div>Your next picks: {escape(upcoming_label)}</div>
            <div>Recent run: {escape(_text(state.get('positional_run'), 'No picks logged yet.'))}</div>
        </div>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def _prestige_level(tier: str) -> str:
    normalized = _text(tier).casefold()
    if normalized in {"elite"}:
        return "elite"
    if normalized in {"star", "core starter", "starter"}:
        return "starter"
    if normalized in {"upside", "development", "developmental"}:
        return "development"
    return "depth"


def _recommendation_html(rec: dict[str, Any]) -> str:
    adp_delta = rec.get("adp_delta")
    adp_text = (
        f"{adp_delta:+.1f} vs ADP"
        if adp_delta is not None
        else "ADP unavailable"
    )
    role = _text(rec.get("recommendation_role"), "Alternative")
    confidence = _text(rec.get("confidence"), "Moderate")
    need = _text(rec.get("position_need_impact"))
    reason = _concise_reason(rec.get("recommendation_reason") or rec.get('reason'))
    tags = "".join(
        football_assets.status_chip_html(label, tone=tone)
        for label, tone in (
            (role, "information"),
            (f"{confidence} confidence", "neutral"),
            (need, "success"),
        )
        if label
    )
    details = (
        "<div class='live-draft-rec-executive'>"
        f"<p class='live-draft-rec-why'>{escape(reason)}</p>"
        "<div class='live-draft-rec-analysis'>"
        f"<span><strong>Roster impact</strong>{escape(_text(rec.get('immediate_roster_impact')))}</span>"
        f"<span><strong>Value vs ADP</strong>{escape(adp_text)}</span>"
        "</div>"
        "</div>"
    )
    asset = football_assets.FootballPlayerAsset(
        player_id=_text(rec.get("player_id")),
        display_name=_text(rec.get("name"), "Player"),
        position=_text(rec.get("position"), "PLAYER"),
        team=_text(rec.get("team"), "FA"),
        prestige_label=_text(rec.get("tier"), "Depth"),
        prestige_level=_prestige_level(_text(rec.get("tier"))),
        value_label="Draft score",
        value=_score(rec.get("league_adjusted_draft_score")),
        insight="",
        age=(f"Age {live_draft.safe_int(rec.get('age'), 0)}" if live_draft.safe_int(rec.get("age"), 0) else ""),
    )
    return football_assets.player_card_html(
        asset,
        density="compact",
        mode="action-enabled",
        tags_html=tags,
        details_html=details,
        extra_classes=("live-draft-rec-card",),
    )


def _render_recommendations(
    state: dict[str, Any],
    *,
    render_tappable_player_html: Callable[..., str] | None = None,
    open_player_quick_view: Callable[..., None] | None = None,
    draft_id: str = "",
) -> None:
    recs = state.get("recommendations") or []
    st.markdown(
        "<div class='live-draft-section-head'><span>Who should I draft next?</span><small>Primary pick first: why, impact, then supporting board context.</small></div>",
        unsafe_allow_html=True,
    )
    if not recs:
        st.info("No recommendations are available yet. Load a league roster and draft board first.")
        return
    html = "<div class='live-draft-rec-grid'>" + "".join(_recommendation_html(rec) for rec in recs) + "</div>"
    if render_tappable_player_html and open_player_quick_view:
        clicked = render_tappable_player_html(
            html=html,
            key_prefix=f"live_draft_recommendations_{draft_id or 'active'}",
        )
        if clicked:
            selected = next((rec for rec in recs if _text(rec.get("player_id")) == clicked), {})
            open_player_quick_view(
                clicked,
                source_label="Live Draft Assistant",
                source_note=_text(selected.get("recommendation_reason")),
                status_label=_text(selected.get("recommendation_role")),
            )
        return
    st.markdown(html, unsafe_allow_html=True)


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
    from modules import canonical_player_ranking

    canonical = canonical_player_ranking.format_compact_rank(
        row.get("canonical_overall_rank"),
        row.get("canonical_position_rank"),
        pos,
        unavailable_reason=row.get("rank_unavailable_reason"),
    )
    ranking_format = _text(row.get("rank_scoring_format"))
    canonical_meta = (
        f"{canonical}"
        + (f" · {ranking_format}" if ranking_format and canonical != "Rank unavailable" else "")
    )
    meta = " · ".join(
        part for part in [
            pos,
            _text(row.get("team")),
            f"Age {live_draft.safe_int(row.get('age'), 0)}" if live_draft.safe_int(row.get("age"), 0) else "",
        ] if part
    )
    html = f"""
    <article class='live-rank-row' data-player-id='{escape(_text(row.get("player_id")), quote=True)}'>
        <div class='live-rank-number'>#{rank}</div>
        <div class='live-rank-main'>
            <div class='live-rank-topline'>
                <span class='live-rank-name'>{escape(_text(row.get('name'), 'Player'))}</span>
                {label_html}{movement_html}
            </div>
            <div class='live-rank-meta'>{escape(meta)} · Board {pos} #{pos_rank} · {escape(canonical_meta)}</div>
            <div class='live-rank-reason'>{escape(_text(row.get('recommendation_reason')))}</div>
        </div>
        <div class='live-rank-score'>
            <strong>{_score(row.get('league_adjusted_draft_score'))}</strong>
            <small>Value {_score(row.get('base_value'))}</small>
        </div>
    </article>
    """
    return "".join(line.strip() for line in html.splitlines())



def ranking_card_styles_html() -> str:
    return (
        "<style>"
        ".live-rank-list{display:grid;gap:var(--space-sm);margin:var(--space-sm) 0 var(--space-lg)}"
        ".live-rank-row{align-items:center;background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);border-radius:var(--radius-sm);display:grid;gap:var(--space-sm);grid-template-columns:2.6rem minmax(0,1fr) auto;padding:var(--space-md)}"
        ".live-rank-number{color:var(--color-accent);font-size:1rem;font-weight:var(--font-weight-display);text-align:center}"
        ".live-rank-main{min-width:0}.live-rank-topline{align-items:center;display:flex;flex-wrap:wrap;gap:.35rem}"
        ".live-rank-name{color:var(--color-text-primary);font:var(--font-card-title)}.live-rank-label{background:var(--color-information-soft);border:var(--border-width-default) solid var(--color-information);border-radius:var(--radius-pill);color:var(--color-information);font-size:var(--font-size-badge);font-weight:var(--font-weight-title);padding:var(--space-xs) var(--space-sm);text-transform:uppercase}"
        ".live-rank-move{color:var(--color-success);font-size:var(--font-size-caption);font-weight:var(--font-weight-title)}.live-rank-meta,.live-rank-reason{color:var(--color-text-muted);font-size:var(--font-size-caption);line-height:var(--line-height-caption);margin-top:var(--space-xs)}.live-rank-reason{color:var(--color-text-secondary)}"
        ".live-rank-score{text-align:right}.live-rank-score strong{color:var(--color-text-primary);display:block;font-size:var(--font-size-card-title)}.live-rank-score small{color:var(--color-text-muted);display:block;font-size:var(--font-size-badge);white-space:nowrap}"
        "@media(max-width:640px){.live-rank-row{gap:.48rem;grid-template-columns:2.15rem minmax(0,1fr) auto;padding:.58rem .5rem}.live-rank-number{font-size:.88rem}.live-rank-name{font-size:.86rem}.live-rank-reason{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.live-rank-score strong{font-size:.82rem}}"
        "</style>"
    )


def _team_ranking_row_html(row: dict[str, Any]) -> str:
    label = _text(row.get("trend_label"))
    label_html = f"<span class='live-rank-label'>{escape(label)}</span>" if label else ""
    movement = _movement_label(row.get("movement"))
    movement_html = f"<span class='live-rank-move'>{escape(movement)}</span>" if movement != "—" else ""
    mine = " · Your Team" if row.get("is_mine") else ""
    html = f"""
    <article class='live-rank-row'>
        <div class='live-rank-number'>#{live_draft.safe_int(row.get('team_rank'), 0)}</div>
        <div class='live-rank-main'>
            <div class='live-rank-topline'>
                <span class='live-rank-name'>{escape(_text(row.get('team_name'), 'Team'))}</span>
                {label_html}{movement_html}
            </div>
            <div class='live-rank-meta'>{live_draft.safe_int(row.get('roster_count'), 0)} players · {live_draft.safe_int(row.get('pick_count'), 0)} draft picks · {escape(_text(row.get('positions'), 'No players yet'))}{escape(mine)}</div>
            <div class='live-rank-reason'>Top player: {escape(_text(row.get('top_player'), 'No players yet'))} · Starters {_score(row.get('starter_value'))} · Total {_score(row.get('total_value'))}</div>
        </div>
        <div class='live-rank-score'>
            <strong>{live_draft.safe_int(row.get('live_team_score'), 0)}</strong>
            <small>Live score</small>
        </div>
    </article>
    """
    return "".join(line.strip() for line in html.splitlines())


def _render_live_team_rankings(state: dict[str, Any]) -> None:
    board = state.get("team_rankings")
    st.markdown(
        ranking_card_styles_html()
        + "<div class='live-draft-section-head'><span>Live Team Rankings</span>"
        + "<small>Every fantasy roster reranked as Sleeper reports each pick.</small></div>",
        unsafe_allow_html=True,
    )
    if board is None or board.empty:
        st.info("Team rankings will appear when draft rosters are available.")
        return
    st.markdown(
        "<div class='live-rank-list'>"
        + "".join(_team_ranking_row_html(row) for row in board.to_dict("records"))
        + "</div>",
        unsafe_allow_html=True,
    )
    with st.expander("How team rankings work", expanded=False):
        st.caption(
            "The live score ranks the complete roster: 60% starter strength, 30% total roster value, "
            "7% usable depth, and 3% lineup coverage. Existing players and drafted players are combined and deduplicated. "
            "There is no separate youth bonus."
        )


def _render_live_rankings(
    state: dict[str, Any],
    *,
    score_label: str,
    open_trade_hub_for_player: Callable[[str], None] | None = None,
) -> None:
    board = state.get("rankings")
    st.markdown(
        """
        <div class='live-draft-section-head'><span>Available Player Rankings</span><small>Every undrafted player, reranked for this league and your roster.</small></div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(ranking_card_styles_html(), unsafe_allow_html=True)
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
    visible_board = display.head(120)
    st.markdown(
        "<div class='live-rank-list'>" + "".join(
            _ranking_row_html(row) for row in visible_board.to_dict("records")
        ) + "</div>",
        unsafe_allow_html=True,
    )
    if len(display) > len(visible_board):
        st.caption(
            f"Showing the top {len(visible_board)} of {len(display)} ranked players. "
            "All available players are still evaluated; use position filters or search for a narrower board."
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
        detail_df = display[[col for col in detail_columns if col in display.columns]].head(25)
        detail_df = detail_df.rename(
            columns={
                "overall_rank": "Rank",
                "name": "Player",
                "base_value": "Base",
                "format_adjustment": "Format",
                "scarcity_score": "Scarcity",
                "roster_fit_score": "Fit",
                "age_strategy_adjustment": "Age/Strategy",
                "availability_adjustment": "Availability",
                "league_adjusted_draft_score": "Live Score",
            }
        )
        executive_table_ui.render_executive_table_disclosure(
            detail_df,
            title="Score breakdown preview",
            primary_column="Player",
            secondary_columns=("Rank", "Live Score"),
            meta_column="Fit",
            max_summary_rows=8,
            include_expander=False,
            key_suffix="live_draft_score_detail",
        )
    player_options = {
        f"#{live_draft.safe_int(row.get('overall_rank'), 0)} {_text(row.get('name'), 'Player')}": row
        for row in display.head(75).to_dict("records")
    }
    if player_options:
        selected = st.selectbox("Player Quick View", list(player_options), key="live_draft_quick_view")
        row = player_options[selected]
        with st.expander(f"Quick View · {_text(row.get('name'), 'Player')}", expanded=False):
            st.caption(
                f"Board #{live_draft.safe_int(row.get('overall_rank'), 0)} · "
                f"{_text(row.get('position')).upper()} board #{live_draft.safe_int(row.get('position_rank'), 0)} · "
                f"{_text(row.get('tier'))}"
            )
            from modules import canonical_player_ranking

            st.caption(
                canonical_player_ranking.format_compact_rank(
                    row.get("canonical_overall_rank"),
                    row.get("canonical_position_rank"),
                    row.get("position"),
                    unavailable_reason=row.get("rank_unavailable_reason"),
                )
                + (
                    f" · {_text(row.get('rank_scoring_format'))}"
                    if _text(row.get("rank_scoring_format"))
                    else ""
                )
            )
            st.write(_text(row.get("recommendation_reason")))
            st.caption(
                f"Base {_score(row.get('base_value'))} | Format {_score(row.get('format_adjustment'))} | "
                f"Scarcity {_score(row.get('scarcity_score'))} | Fit {_score(row.get('roster_fit_score'))} | "
                f"Age/strategy {_score(row.get('age_strategy_adjustment'))} | Availability {_score(row.get('availability_adjustment'))}"
            )
            player_id = _text(row.get("player_id"))
            if open_trade_hub_for_player is not None and player_id:
                st.button(
                    "Open in Trade Hub",
                    key=f"live_rank_trade_{player_id}",
                    use_container_width=True,
                    on_click=open_trade_hub_for_player,
                    args=(player_id,),
                )
            elif st.button(
                "Open in Trade Hub",
                key=f"live_rank_trade_{player_id}",
                use_container_width=True,
            ):
                league_id = str(st.session_state.get("selected_league_id") or "").strip()
                st.session_state["trade_hub_player_id"] = player_id
                if league_id:
                    st.session_state[f"trade_hub_focus_player_id_{league_id}"] = player_id
                    st.session_state[f"trade_hub_focus_mode_{league_id}"] = "target_player"
                st.session_state["current_page"] = "trade_hub"
                st.session_state["platform_nav_page"] = "trade_hub"
                st.rerun()

def _render_team_boards(state: dict[str, Any]) -> None:
    rows = state.get("pick_rows") or []
    with st.expander("Recent picks, your picks, and positional run", expanded=False):
        if not rows:
            st.caption("No pick history is available yet.")
            return
        my_rows = [row for row in rows if row.get("is_mine")]
        st.caption(f"Recent positional run: {_text(state.get('positional_run'))}")

        def _pick_rows_df(pick_rows: list[dict]) -> pd.DataFrame:
            frame = pd.DataFrame(pick_rows).drop(columns=["raw"], errors="ignore")
            rename = {
                "pick_no": "Pick",
                "round": "Round",
                "name": "Player",
                "position": "Pos",
                "fantasy_team": "Team",
            }
            return frame.rename(columns={key: value for key, value in rename.items() if key in frame.columns})

        recent_df = _pick_rows_df(rows[-12:])
        executive_table_ui.render_executive_table_disclosure(
            recent_df,
            title="Recent picks",
            primary_column="Player" if "Player" in recent_df.columns else recent_df.columns[0],
            secondary_columns=tuple(
                column for column in ("Pick", "Round", "Pos", "Team") if column in recent_df.columns
            ),
            max_summary_rows=8,
            include_expander=False,
            key_suffix="live_draft_recent_picks",
        )
        if my_rows:
            my_df = _pick_rows_df(my_rows)
            executive_table_ui.render_executive_table_disclosure(
                my_df,
                title="Your selections",
                primary_column="Player" if "Player" in my_df.columns else my_df.columns[0],
                secondary_columns=tuple(
                    column for column in ("Pick", "Round", "Pos") if column in my_df.columns
                ),
                max_summary_rows=8,
                include_expander=False,
                key_suffix="live_draft_my_picks",
            )

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
            by_team = by_team.rename(columns={"fantasy_team": "Team"})
            executive_table_ui.render_executive_table_disclosure(
                by_team,
                title="Picks by team",
                primary_column="Team",
                meta_column="Positions",
                max_summary_rows=10,
                include_expander=False,
                key_suffix="live_draft_team_summary",
            )


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
    render_tappable_player_html: Callable[..., str] | None = None,
    open_player_quick_view: Callable[..., None] | None = None,
    open_trade_hub_for_player: Callable[[str], None] | None = None,
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

    live_drafts = [
        draft
        for draft in drafts
        if live_draft.normalize_draft_status(draft.get("status"))
        in live_draft.LIVE_DRAFT_ACTIVE_STATUSES
    ]
    if not live_drafts:
        if any(live_draft.normalize_draft_status(draft.get("status")) == "complete" for draft in drafts):
            st.info("The latest Sleeper draft has ended. Live Draft activates again when a draft is in progress or paused.")
        else:
            st.info("No live Sleeper draft is active. This workspace appears only while a draft is in progress or paused.")
        return

    labels = [_draft_label(draft) for draft in live_drafts]
    default_index = 0
    selected_label = st.selectbox("Draft", labels, index=default_index, key=f"live_draft_selector_{selected_league_id}")
    selected_draft = live_drafts[labels.index(selected_label)]
    draft_id = _text(selected_draft.get("draft_id"))
    state_key = f"live_draft_last_state_{draft_id}"
    signature_key = f"live_draft_state_signature_{draft_id}"

    def invalidate_live_draft_state() -> None:
        st.session_state.pop(signature_key, None)
        performance.mark_interaction("refresh_live_draft", lightweight=False)

    st.button(
        "Refresh Draft",
        key=f"live_draft_refresh_{draft_id}",
        use_container_width=True,
        on_click=invalidate_live_draft_state,
    )

    def render_snapshot() -> None:
        picks, pick_error = fetch_draft_picks(draft_id)
        picks_key = f"live_draft_last_picks_{draft_id}"
        ranks_key = f"live_draft_previous_ranks_{draft_id}"
        team_ranks_key = f"live_draft_previous_team_ranks_{draft_id}"
        if pick_error:
            picks = st.session_state.get(picks_key, picks)
        else:
            st.session_state[picks_key] = picks
        previous_ranks = st.session_state.get(ranks_key, {})
        previous_team_ranks = st.session_state.get(team_ranks_key, {})
        draft_detail = fetch_draft(draft_id) or selected_draft
        draft_detail = {**selected_draft, **draft_detail, "draft_id": draft_id}
        signature = live_draft.draft_state_signature(picks, draft_detail)
        cached_signature = st.session_state.get(signature_key)
        cached_state = st.session_state.get(state_key)
        can_reuse = isinstance(cached_state, dict) and (
            pick_error or cached_signature == signature
        )
        if can_reuse:
            state = cached_state
            performance.record_cache_event(
                "live_draft_state",
                "hit",
                result_size=len(state.get("rankings", [])),
                invalidation_reason="unchanged_draft_state" if not pick_error else "temporary_sleeper_failure",
            )
        else:
            build_started = time.perf_counter()
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
                previous_team_ranks=previous_team_ranks,
            )
            if not pick_error:
                st.session_state[state_key] = state
                st.session_state[signature_key] = signature
            performance.record_cache_event(
                "live_draft_state",
                "miss",
                elapsed_ms=(time.perf_counter() - build_started) * 1000,
                result_size=len(state.get("rankings", [])),
                invalidation_reason="draft_state_changed",
            )
        rankings = state.get("rankings")
        if rankings is not None and not rankings.empty and not pick_error:
            st.session_state[ranks_key] = {
                _text(row.get("player_id")): live_draft.safe_int(row.get("overall_rank"), 0)
                for row in rankings.to_dict("records") if _text(row.get("player_id"))
            }
        team_rankings = state.get("team_rankings")
        if team_rankings is not None and not team_rankings.empty and not pick_error:
            st.session_state[team_ranks_key] = {
                str(row.get("roster_id")): live_draft.safe_int(row.get("team_rank"), 0)
                for row in team_rankings.to_dict("records")
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
        with performance.time_block("live_draft_ui_render", category="render"):
            _render_on_clock(state)
            _render_recommendations(
                state,
                render_tappable_player_html=render_tappable_player_html,
                open_player_quick_view=open_player_quick_view,
                draft_id=draft_id,
            )
            _render_live_team_rankings(state)
            _render_live_rankings(
                state,
                score_label=score_label,
                open_trade_hub_for_player=open_trade_hub_for_player,
            )
            _render_pick_board(state)
            _render_team_boards(state)

    if hasattr(st, "fragment") and live_draft.normalize_draft_status(selected_draft.get("status")) != "complete":
        @st.fragment(run_every=f"{poll_interval_seconds}s")
        def live_draft_fragment():
            render_snapshot()

        live_draft_fragment()
    else:
        render_snapshot()
