import os
from html import escape
from typing import Callable

import pandas as pd
import streamlit as st


DECISION_BUCKET_STATUS_LABELS = {
    "move": "Move Now",
    "trade": "Trade Candidate",
    "drop": "Drop Candidate",
    "keep": "Hold",
}

SEMANTIC_ICONS = {
    "dashboard": "*",
    "home": "*",
    "my_team": "@",
    "roster": "@",
    "teams": "@",
    "trade": "$",
    "trade_hub": "$",
    "league": "LG",
    "rankings": "#",
    "draft": "#",
    "draft_summary": "#",
    "waivers": "+",
    "waiver": "+",
    "players": "PL",
    "news": "NW",
    "all": ">",
    "alert": "!",
    "risk": "!",
    "injury": "IR",
    "health": "IR",
    "action": ">",
    "move": ">",
    "opportunity": "+",
    "value": "$",
    "rising": "UP",
    "stash": "ST",
    "core": "C",
    "starter": "S",
    "bench": "B",
    "hold": "H",
    "protect": "P",
    "drop": "X",
    "taxi": "TX",
    "review": "RV",
    "recap": "RV",
    "grade": "A",
    "diagnostic": "DG",
    "metric": "#",
    "power": "PW",
    "franchise": "FR",
    "strategy": "ST",
    "score": "SC",
}

SUMMARY_TILE_EXPLANATIONS = {
    "power rank": "Current league strength based on present roster quality and weekly usable lineup power.",
    "franchise rank": "Longer-term franchise value using roster value, age curve, depth, and draft capital context.",
    "team direction": "The app's current read on whether this roster should contend, retool, or build for future value.",
    "strategy": "Recommended team lens for how aggressive the roster should be in trades, waivers, and roster cuts.",
    "archetype": "A more specific roster profile used to frame trade posture and roster-building priorities.",
    "health status": "Availability outlook based on injured starters and the position rooms most affected.",
    "health outlook": "Availability outlook based on injured starters and the position rooms most affected.",
    "starter unit": "Snapshot of the usable starter group relative to the rest of the league.",
    "weak positions": "Position rooms most likely to drive trade, waiver, or depth attention.",
    "strength positions": "Position rooms with enough depth or value to support consolidation, holds, or trade-away decisions.",
}


SUMMARY_TILE_TAP_COMPONENT = st.components.v2.component(
    "summary_tile_tap_grid",
    html="""
    <div id="summary-tile-tap-root"></div>
    """,
    js="""
    export default function(component) {
      const { data, parentElement, setTriggerValue } = component
      const root = parentElement.querySelector("#summary-tile-tap-root")
      if (!root) return

      root.innerHTML = (data && data.html) || ""

      const emit = (tile) => {
        if (!tile) return
        const index = tile.dataset.summaryIndex || tile.getAttribute("data-summary-index") || ""
        if (index) setTriggerValue("clicked", { index, ts: Date.now() })
      }

      root.querySelectorAll(".summary-tile-tappable[data-summary-index]").forEach((tile) => {
        if (!tile.hasAttribute("tabindex")) tile.setAttribute("tabindex", "0")
        if (!tile.hasAttribute("role")) tile.setAttribute("role", "button")

        tile.onclick = (event) => {
          event.stopPropagation()
          emit(tile)
        }

        tile.onkeydown = (event) => {
          if (event.key !== "Enter" && event.key !== " ") return
          event.preventDefault()
          event.stopPropagation()
          emit(tile)
        }
      })
    }
    """,
    isolate_styles=False,
)


def debug_ui_enabled() -> bool:
    return str(os.environ.get("DYNASTYGM_DEBUG_UI") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def semantic_icon(kind: str) -> str:
    key = _safe_text(kind).strip().lower().replace(" ", "_").replace("-", "_")
    return SEMANTIC_ICONS.get(key, SEMANTIC_ICONS.get(key.split("_")[0], "•"))


def semantic_icon_html(kind: str, *, label: str | None = None) -> str:
    icon = semantic_icon(kind)
    aria = _safe_text(label or kind, "section")
    return (
        "<span class='dg-semantic-icon' aria-hidden='true'>"
        + escape(icon)
        + "</span>"
        + f"<span class='sr-only'>{escape(aria)} icon</span>"
    )


def summary_tile_explanation(label: str) -> str:
    key = _safe_text(label).strip().casefold()
    return SUMMARY_TILE_EXPLANATIONS.get(
        key,
        "This tile summarizes one part of the current roster or league context using the app's existing analysis.",
    )


def summary_tile_detail_html(item: dict) -> str:
    label = _safe_text(item.get("label"), "Summary")
    value = _safe_text(item.get("value"), "-")
    note = _safe_text(item.get("note"))
    explanation = _safe_text(item.get("detail") or item.get("explanation") or summary_tile_explanation(label))
    supporting = _safe_text(item.get("supporting_context") or item.get("context"))
    detail_items = item.get("detail_items") or item.get("detail_rows") or []
    rows = [
        ("Current Value", value),
        ("What It Means", explanation),
    ]
    if note:
        rows.append(("Context", note))
    if supporting:
        rows.append(("Supporting Detail", supporting))
    row_html = "".join(
        "<div class='summary-detail-row'>"
        + f"<div class='summary-detail-row-label'>{escape(row_label)}</div>"
        + f"<div class='summary-detail-row-value'>{escape(row_value)}</div>"
        + "</div>"
        for row_label, row_value in rows
    )
    list_html = ""
    if detail_items:
        detail_rows = []
        for detail in detail_items:
            if isinstance(detail, dict):
                title = _safe_text(detail.get("title") or detail.get("label") or detail.get("team") or detail.get("name"))
                value_text = _safe_text(detail.get("value") or detail.get("rank") or detail.get("score"))
                note_text = _safe_text(detail.get("note") or detail.get("context") or detail.get("summary"))
                highlight_class = " summary-detail-list-row-current" if detail.get("current") or detail.get("highlight") else ""
            else:
                title = _safe_text(detail)
                value_text = ""
                note_text = ""
                highlight_class = ""
            if not title and not value_text and not note_text:
                continue
            detail_rows.append(
                "<div class='summary-detail-list-row"
                + highlight_class
                + "'>"
                + "<div class='summary-detail-list-main'>"
                + f"<span class='summary-detail-list-title'>{escape(title)}</span>"
                + (f"<span class='summary-detail-list-note'>{escape(note_text)}</span>" if note_text else "")
                + "</div>"
                + (f"<div class='summary-detail-list-value'>{escape(value_text)}</div>" if value_text else "")
                + "</div>"
            )
        if detail_rows:
            list_title = _safe_text(item.get("detail_items_title"), "Supporting Context")
            list_html = (
                "<div class='summary-detail-list'>"
                + f"<div class='summary-detail-list-heading'>{escape(list_title)}</div>"
                + "".join(detail_rows)
                + "</div>"
            )
    return (
        "<div class='summary-detail-panel dg-panel-list'>"
        + "<div class='summary-detail-header'>"
        + f"<div class='summary-detail-kicker'>{semantic_icon_html(label, label=label)}Metric Detail</div>"
        + f"<div class='summary-detail-title'>{escape(label)}</div>"
        + f"<div class='summary-detail-value'>{escape(value)}</div>"
        + "</div>"
        + f"<div class='summary-detail-rows'>{row_html}</div>"
        + list_html
        + "</div>"
    )


def _render_summary_tile_detail_dialog(item: dict) -> None:
    label = _safe_text(item.get("label"), "Summary")

    @st.dialog(label)
    def _dialog():
        st.markdown(summary_tile_detail_html(item), unsafe_allow_html=True)

    _dialog()


def render_team_identity_card(
    team_profile: dict,
    selected_league_name: str,
    metrics: dict | None,
    *,
    format_score: Callable,
    glyph_chip_html: Callable,
    team_initials: Callable,
    team_strategy_label: Callable,
):
    team_name = _safe_text(team_profile.get("team_name"), "My Team")
    owner_name = _safe_text(
        team_profile.get("owner_name"),
        _safe_text(team_profile.get("username"), "Sleeper roster"),
    )
    avatar_url = _safe_text(team_profile.get("avatar_url"))
    strategy = _safe_text(metrics.get("strategy_label"), "") if metrics else ""
    archetype = _safe_text(metrics.get("archetype_label"), "") if metrics else ""
    if not strategy and metrics:
        strategy = team_strategy_label(metrics.get("strategy") or metrics.get("mode"))
    strategy = strategy or "Unknown"
    score = format_score(metrics.get("total_score")) if metrics else "0"
    league = _safe_text(selected_league_name, "Selected league")
    chips = [
        glyph_chip_html(owner_name or "Sleeper roster", "primary"),
        glyph_chip_html(strategy, "success"),
    ]
    if archetype:
        chips.append(glyph_chip_html(archetype, "warning"))
    chips.append(glyph_chip_html(f"Score {score}", "premium"))

    if avatar_url:
        logo_html = f"<img src='{escape(avatar_url, quote=True)}' alt='' loading='lazy'>"
    else:
        logo_html = escape(team_initials(team_name))

    html = f"""
    <div class="team-identity-card dg-card-secondary">
        <div class="team-logo-wrap">{logo_html}</div>
        <div class="team-identity-copy">
            <div class="team-kicker">{escape(league)}</div>
            <div class="team-name">{escape(team_name)}</div>
            <div class="team-subtitle">Franchise identity and current team lens.</div>
            <div class="team-identity-badges">{''.join(chips)}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_section_header(
    title: str,
    kicker: str = "",
    note: str = "",
    compact: bool = False,
):
    classes = "section-header section-header-compact" if compact else "section-header"
    kicker_html = (
        f"<div class='section-kicker'>{semantic_icon_html(kicker or title, label=title)}{escape(_safe_text(kicker))}</div>"
        if _safe_text(kicker)
        else ""
    )
    note_html = (
        f"<div class='section-note'>{escape(_safe_text(note))}</div>"
        if _safe_text(note)
        else ""
    )
    st.markdown(
        f"<div class='{classes}'>{kicker_html}<div class='section-title'>{escape(_safe_text(title))}</div>{note_html}</div>",
        unsafe_allow_html=True,
    )


def render_concept_band(items: list[dict]):
    chips = []
    for item in items:
        label = _safe_text(item.get("label"))
        title = _safe_text(item.get("title"))
        body = _safe_text(item.get("body"))
        tone = _safe_text(item.get("tone"), "power").lower()
        chips.append(
            "<div class='concept-chip concept-chip-"
            + escape(tone)
            + "'>"
            + f"<div class='concept-label'>{escape(label)}</div>"
            + f"<div class='concept-title'>{escape(title)}</div>"
            + f"<div class='concept-body'>{escape(body)}</div>"
            + "</div>"
        )
    if chips:
        st.markdown(
            "<div class='concept-band'>" + "".join(chips) + "</div>",
            unsafe_allow_html=True,
        )


def render_summary_tiles(items: list[dict], *, compact: bool = False):
    cards = []
    for idx, item in enumerate(items):
        label = _safe_text(item.get("label"))
        value = _safe_text(item.get("value"))
        note = _safe_text(item.get("note"))
        tone = _safe_text(item.get("tone"), "").strip().lower()
        tone_class = f" summary-tile-{tone}" if tone else ""
        compact_class = " summary-tile-compact" if compact else ""
        semantic_class = " dg-card-reference"
        if tone in {"power", "opportunity"}:
            semantic_class = " dg-card-primary"
        elif tone in {"risk", "weakness"}:
            semantic_class = " dg-card-warning"
        elif tone in {"franchise", "strategy"}:
            semantic_class = " dg-card-secondary"
        cards.append(
            "<div class='summary-tile"
            + tone_class
            + compact_class
            + semantic_class
            + " summary-tile-tappable"
            + f"' data-summary-index='{idx}' aria-label='View details for {escape(label, quote=True)}'>"
            + "<div class='summary-tile-top'><span class='summary-tile-dot'></span>"
            + f"<div class='summary-tile-label'>{semantic_icon_html(tone or label, label=label)}{escape(label)}</div></div>"
            + f"<div class='summary-tile-value'>{escape(value)}</div>"
            + f"<div class='summary-tile-note'>{escape(note)}</div>"
            + "<div class='summary-tile-affordance' aria-hidden='true'>View</div>"
            + "</div>"
        )
    if cards:
        grid_class = (
            "summary-tile-grid summary-tile-grid-compact"
            if compact
            else "summary-tile-grid"
        )
        html = f"<div class='{grid_class}'>" + "".join(cards) + "</div>"
        try:
            result = SUMMARY_TILE_TAP_COMPONENT(
                key=f"summary_tile_tap_{abs(hash(html))}",
                data={"html": html},
                width="stretch",
                height="content",
                on_clicked_change=lambda: None,
            )
        except ValueError as exc:
            if "is not registered" not in str(exc):
                raise
            st.markdown(html, unsafe_allow_html=True)
            return
        clicked = getattr(result, "clicked", None)
        if isinstance(clicked, dict):
            try:
                clicked_index = int(clicked.get("index"))
            except Exception:
                clicked_index = -1
            if 0 <= clicked_index < len(items):
                _render_summary_tile_detail_dialog(items[clicked_index])


def render_analysis_cards(cards: list[dict]):
    html_cards = []
    for card in cards:
        title = _safe_text(card.get("title"))
        label = _safe_text(card.get("label"))
        tone = _safe_text(card.get("tone"), "risk").lower()
        semantic_class = (
            " dg-card-secondary"
            if tone == "strength"
            else " dg-card-warning"
            if tone in {"risk", "weakness"}
            else " dg-card-reference"
        )
        items = card.get("items") or []
        item_html = "".join(
            f"<li>{escape(_safe_text(item))}</li>"
            for item in items
            if _safe_text(item)
        ) or "<li>No notable signal yet.</li>"
        html_cards.append(
            "<div class='analysis-card analysis-card-"
            + escape(tone)
            + semantic_class
            + "'>"
            + "<div class='analysis-card-top'><span class='analysis-card-dot'></span>"
            + f"<div class='analysis-card-label'>{semantic_icon_html(tone or label, label=label)}{escape(label)}</div></div>"
            + f"<div class='analysis-card-title'>{escape(title)}</div>"
            + "<ul class='analysis-list'>"
            + item_html
            + "</ul></div>"
        )
    if html_cards:
        st.markdown(
            "<div class='analysis-grid'>" + "".join(html_cards) + "</div>",
            unsafe_allow_html=True,
        )


def _decision_bucket_status_label(bucket: str) -> str:
    bucket_key = _safe_text(bucket).strip().lower()
    return DECISION_BUCKET_STATUS_LABELS.get(bucket_key, "Hold")


def render_structured_decision_cards(
    cards: list[dict],
    *,
    container_class: str = "",
    player_scan_card_html: Callable,
    compact_player_row_html: Callable | None = None,
    recommendation_reason_text: Callable,
    render_tappable_player_html: Callable | None = None,
    open_player_quick_view: Callable | None = None,
    key_prefix: str = "structured_decisions",
):
    html_cards = []
    quick_view_meta: dict[str, dict[str, str]] = {}
    for card in cards:
        title = _safe_text(card.get("title"))
        label = _safe_text(card.get("label"))
        tone = _safe_text(card.get("tone"), "reference").lower()
        candidates = [
            item for item in (card.get("candidates") or []) if isinstance(item, dict)
        ]
        empty_note = _safe_text(card.get("empty_note"), "No notable signal yet.")
        semantic_class = (
            " dg-card-secondary decision-panel-strength"
            if tone == "strength"
            else " dg-card-warning decision-panel-risk"
            if tone in {"risk", "weakness", "warning"}
            else " dg-card-reference decision-panel-reference"
        )
        rows_html = []
        for item in candidates:
            status_label = _decision_bucket_status_label(item.get("bucket"))
            reason = recommendation_reason_text(
                _safe_text(item.get("reason") or item.get("note")),
                104,
            )
            player_row = dict(item)
            player_row["name"] = _safe_text(
                item.get("name") or item.get("player_name"),
                "Roster player",
            )
            player_row["value_score"] = item.get(
                "score",
                item.get("value_score", 0),
            )
            player_id = _safe_text(item.get("player_id")).strip()
            row_builder = compact_player_row_html or player_scan_card_html
            if compact_player_row_html:
                rows_html.append(
                    row_builder(
                        player_row,
                        score_field="value_score",
                        score_label="Value",
                        status_label=status_label,
                        note_text=reason,
                        interactive=bool(player_id),
                    )
                )
            else:
                rows_html.append(
                    row_builder(
                        player_row,
                        score_field="value_score",
                        score_label="Value",
                        status_label=status_label,
                        note_text=reason,
                        compact=True,
                        interactive=bool(player_id),
                        show_inline_reason=True,
                    )
                )
            if player_id:
                quick_view_meta[player_id] = {
                    "source_label": label or title,
                    "source_note": reason,
                    "status_label": status_label,
                }
        body_html = (
            "<div class='decision-panel-body scan-card-list scan-card-list-compact'>"
            + "".join(rows_html)
            + "</div>"
            if rows_html
            else f"<div class='decision-panel-empty'>{escape(empty_note)}</div>"
        )
        html_cards.append(
            "<div class='decision-panel"
            + semantic_class
            + "'>"
            + "<div class='decision-panel-top'><span class='decision-panel-dot'></span>"
            + f"<div class='decision-panel-label'>{semantic_icon_html(tone or label, label=label)}{escape(label)}</div></div>"
            + f"<div class='decision-panel-title'>{escape(title)}</div>"
            + body_html
            + "</div>"
        )
    if html_cards:
        grid_classes = "decision-panel-grid"
        if _safe_text(container_class).strip():
            grid_classes += " " + _safe_text(container_class).strip()
        grid_html = (
            f"<div class='{grid_classes}'>" + "".join(html_cards) + "</div>"
        )
        if (
            render_tappable_player_html is not None
            and open_player_quick_view is not None
            and quick_view_meta
        ):
            clicked_player_id = render_tappable_player_html(
                html=grid_html,
                key_prefix=key_prefix,
            )
            if clicked_player_id in quick_view_meta:
                meta = quick_view_meta[clicked_player_id]
                open_player_quick_view(
                    clicked_player_id,
                    source_label=meta["source_label"],
                    source_note=meta["source_note"],
                    status_label=meta["status_label"],
                )
        else:
            st.markdown(grid_html, unsafe_allow_html=True)


def render_roster_utility_debug(
    debug_rows: list[dict] | None,
    *,
    title: str = "Decision Debug: Lowest Roster Utility",
):
    if not debug_ui_enabled():
        return
    rows = [item for item in (debug_rows or []) if isinstance(item, dict)]
    if not rows:
        return
    with st.expander(title, expanded=False):
        debug_df = pd.DataFrame(
            [
                {
                    "Player": _safe_text(
                        item.get("player_name") or item.get("name")
                    ),
                    "Pos": _safe_text(item.get("position")),
                    "Team": _safe_text(item.get("team"), "FA"),
                    "Action": _safe_text(item.get("action_label"), "Monitor"),
                    "Utility": round(
                        _safe_float(item.get("roster_utility_score"), 0.0),
                        1,
                    ),
                    "Reason": _safe_text(item.get("reason")),
                }
                for item in rows
            ]
        )
        st.dataframe(debug_df, use_container_width=True, hide_index=True)


def render_no_team_player_debug(
    debug_rows: list[dict] | None,
    *,
    title: str = "Decision Debug: Rostered No-Team / FA Players",
):
    if not debug_ui_enabled():
        return
    rows = [item for item in (debug_rows or []) if isinstance(item, dict)]
    if not rows:
        return
    with st.expander(title, expanded=False):
        debug_df = pd.DataFrame(
            [
                {
                    "player_id": _safe_text(item.get("player_id")),
                    "Player": _safe_text(
                        item.get("player_name") or item.get("name")
                    ),
                    "Pos": _safe_text(item.get("position")),
                    "Team": _safe_text(item.get("team"), "FA"),
                    "Status": _safe_text(item.get("status")),
                    "Active": "Yes" if bool(item.get("active_flag")) else "No",
                    "Search Rank": _safe_positive_int(
                        item.get("search_rank"),
                        0,
                    )
                    or "",
                    "Utility": round(
                        _safe_float(item.get("roster_utility_score"), 0.0),
                        1,
                    ),
                    "Bucket": (
                        "Unsigned / No NFL Team"
                        if bool(item.get("unsigned_no_team_flag"))
                        else "Protected Stash"
                    ),
                    "Reasons": _safe_text(item.get("reason_text")),
                }
                for item in rows
            ]
        )
        st.dataframe(debug_df, use_container_width=True, hide_index=True)


def render_visible_decision_source_debug(
    candidates: list[dict] | None,
    *,
    title: str = "Decision Debug: Visible Drop Candidates Source",
):
    if not debug_ui_enabled():
        return
    rows = [item for item in (candidates or []) if isinstance(item, dict)]
    if not rows:
        return
    with st.expander(title, expanded=False):
        debug_df = pd.DataFrame(
            [
                {
                    "player_id": _safe_text(item.get("player_id")),
                    "name": _safe_text(
                        item.get("player_name") or item.get("name")
                    ),
                    "bucket": _safe_text(item.get("bucket")),
                    "utility_score": round(
                        _safe_float(item.get("roster_utility_score"), 0.0),
                        1,
                    ),
                    "drop_priority": _safe_positive_int(
                        item.get("priority"),
                        0,
                    ),
                    "reason": _safe_text(item.get("reason")),
                }
                for item in rows
            ]
        )
        st.dataframe(debug_df, use_container_width=True, hide_index=True)


def render_home_command_hero(
    *,
    team_profile: dict,
    selected_league_name: str,
    record_label: str = "",
    direction_label: str,
    health_status: str,
    archetype_label: str = "",
    power_rank,
    franchise_rank,
    owner_handle: Callable,
    team_logo_html: Callable,
    format_rank: Callable,
):
    direction_badge = _safe_text(direction_label, "Balanced")
    health_badge = _safe_text(health_status, "Stable")
    archetype_badge = _safe_text(archetype_label)

    html = (
        "<div class='home-command-shell'>"
        + "<div class='home-command-kicker'>Dashboard Command</div>"
        + "<div class='home-command-hero'>"
        + "<div class='home-hero-logo home-hero-logo-command'>GM</div>"
        + "<div>"
        + "<div class='home-command-team'>Next Moves</div>"
        + "<div class='home-command-meta'>Priority roster, trade, waiver, and draft signals for the active franchise.</div>"
        + "<div class='home-command-badges'>"
        + (
            f"<span class='home-command-badge'>{escape(record_label)}</span>"
            if record_label
            else ""
        )
        + (
            f"<span class='home-command-badge home-command-badge-archetype'>{escape(archetype_badge)}</span>"
            if archetype_badge
            else ""
        )
        + "</div>"
        + "<div class='home-hero-stats'>"
        + "<div class='home-hero-stat'>"
        + f"<div class='home-hero-stat-label'>{semantic_icon_html('power', label='Power Rank')}Power Rank</div>"
        + f"<div class='home-hero-stat-value'>{escape(format_rank(power_rank))}</div>"
        + "</div>"
        + "<div class='home-hero-stat'>"
        + f"<div class='home-hero-stat-label'>{semantic_icon_html('franchise', label='Franchise Rank')}Franchise Rank</div>"
        + f"<div class='home-hero-stat-value'>{escape(format_rank(franchise_rank))}</div>"
        + "</div>"
        + "<div class='home-hero-stat'>"
        + f"<div class='home-hero-stat-label'>{semantic_icon_html('strategy', label='Team Direction')}Team Direction</div>"
        + f"<div class='home-hero-stat-value'>{escape(direction_badge)}</div>"
        + "</div>"
        + "<div class='home-hero-stat'>"
        + f"<div class='home-hero-stat-label'>{semantic_icon_html('health', label='Health Status')}Health Status</div>"
        + f"<div class='home-hero-stat-value'>{escape(health_badge)}</div>"
        + "</div>"
        + "</div></div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _recommendation_player_row(
    df_players: pd.DataFrame,
    *,
    player_id: str = "",
    player_name: str = "",
):
    if df_players is None or df_players.empty:
        return None
    player_id = _safe_text(player_id).strip()
    if player_id and "player_id" in df_players.columns:
        matches = df_players[df_players["player_id"].astype(str).eq(player_id)]
        if not matches.empty:
            return matches.iloc[0]
    player_name = _safe_text(player_name).strip()
    if player_name and "name" in df_players.columns:
        matches = df_players[
            df_players["name"]
            .astype(str)
            .str.casefold()
            .eq(player_name.casefold())
        ]
        if not matches.empty:
            return matches.iloc[0]
    return None


def render_home_command_tiles(
    items: list[dict],
    *,
    player_scan_card_html: Callable,
    compact_player_row_html: Callable | None = None,
    render_interactive_html: Callable | None = None,
    render_tappable_player_html: Callable | None = None,
    open_player_quick_view: Callable | None = None,
    open_route_action: Callable | None = None,
    key_prefix: str = "home_command_tiles",
):
    cards = []
    quick_view_meta: dict[str, dict[str, str]] = {}
    route_meta: dict[str, dict[str, str]] = {}
    for item in items:
        label = _safe_text(item.get("label"))
        value = _safe_text(item.get("value"))
        note = _safe_text(item.get("note"))
        tone = _safe_text(item.get("tone"), "trade").lower()
        wide_class = " home-command-card-wide" if item.get("wide") else ""
        route_key = _safe_text(item.get("route_key")).strip()
        route_player_id = _safe_text(item.get("route_player_id")).strip()
        route_focus_mode = _safe_text(item.get("route_focus_mode")).strip()
        route_class = " home-command-route-card" if route_key else ""
        route_attrs = (
            f" data-route='{escape(route_key, quote=True)}'"
            + (
                f" data-route-player-id='{escape(route_player_id, quote=True)}'"
                if route_player_id
                else ""
            )
            + (
                f" data-route-focus-mode='{escape(route_focus_mode, quote=True)}'"
                if route_focus_mode
                else ""
            )
            + " role='button' tabindex='0'"
            + f" aria-label='Open {escape(label or route_key, quote=True)}'"
            if route_key
            else ""
        )
        player_row = item.get("player_row")
        if player_row is not None and hasattr(player_row, "get"):
            player_id = _safe_text(player_row.get("player_id")).strip()
            recommendation_label = _safe_text(
                item.get("recommendation_label"),
                label,
            )
            row_builder = compact_player_row_html or player_scan_card_html
            if compact_player_row_html:
                player_card = row_builder(
                    player_row,
                    score_field=_safe_text(item.get("score_field"), "value_score"),
                    score_label=_safe_text(item.get("score_label"), "Value"),
                    status_label=recommendation_label,
                    note_text=note,
                    interactive=bool(player_id),
                )
            else:
                player_card = row_builder(
                    player_row,
                    score_field=_safe_text(item.get("score_field"), "value_score"),
                    score_label=_safe_text(item.get("score_label"), "Value"),
                    status_label=recommendation_label,
                    note_text=note,
                    compact=True,
                    interactive=bool(player_id),
                    show_inline_reason=True,
                )
            cards.append(
                "<div class='home-command-card home-command-card-"
                + escape(tone)
                + wide_class
                + " home-command-player-card"
                + route_class
                + "'"
                + route_attrs
                + ">"
                + "<div class='home-command-card-top'><span class='home-command-card-dot'></span>"
                + f"<div class='home-command-card-label'>{semantic_icon_html(tone or label, label=label)}{escape(label)}</div>"
                + ("<div class='home-command-card-cta'>Open in Trade Hub</div>" if route_key == "trade_hub" else "")
                + "</div>"
                + player_card
                + "</div>"
            )
            if player_id:
                quick_view_meta[player_id] = {
                    "source_label": label,
                    "source_note": note,
                    "status_label": recommendation_label,
                }
            if route_key:
                route_meta[route_key] = {
                    "route": route_key,
                    "player_id": route_player_id or player_id,
                    "focus_mode": route_focus_mode,
                    "source_label": label,
                    "source_note": note,
                }
            continue
        cards.append(
            "<div class='home-command-card home-command-card-"
            + escape(tone)
            + wide_class
            + "'>"
            + "<div class='home-command-card-top'><span class='home-command-card-dot'></span>"
            + f"<div class='home-command-card-label'>{semantic_icon_html(tone or label, label=label)}{escape(label)}</div></div>"
            + f"<div class='home-command-card-value'>{escape(value)}</div>"
            + f"<div class='home-command-card-note'>{escape(note)}</div>"
            + "</div>"
        )
    if cards:
        grid_html = "<div class='home-command-grid'>" + "".join(cards) + "</div>"
        if (
            render_interactive_html is not None
            and (open_player_quick_view is not None or open_route_action is not None)
            and (quick_view_meta or route_meta)
        ):
            clicked = render_interactive_html(html=grid_html, key_prefix=key_prefix)
            clicked_player_id = _safe_text(clicked.get("player_id")).strip() if isinstance(clicked, dict) else ""
            clicked_route = _safe_text(clicked.get("route")).strip() if isinstance(clicked, dict) else ""
            if clicked_player_id in quick_view_meta and open_player_quick_view is not None:
                meta = quick_view_meta[clicked_player_id]
                open_player_quick_view(
                    clicked_player_id,
                    source_label=meta["source_label"],
                    source_note=meta["source_note"],
                    status_label=meta["status_label"],
                )
            elif clicked_route and open_route_action is not None:
                open_route_action(
                    clicked_route,
                    player_id=_safe_text(clicked.get("player_id")).strip(),
                    focus_mode=_safe_text(clicked.get("focus_mode")).strip(),
                    source_label=_safe_text(route_meta.get(clicked_route, {}).get("source_label")),
                    source_note=_safe_text(route_meta.get(clicked_route, {}).get("source_note")),
                )
        elif (
            render_tappable_player_html is not None
            and open_player_quick_view is not None
            and quick_view_meta
        ):
            clicked_player_id = render_tappable_player_html(
                html=grid_html,
                key_prefix=key_prefix,
            )
            if clicked_player_id in quick_view_meta:
                meta = quick_view_meta[clicked_player_id]
                open_player_quick_view(
                    clicked_player_id,
                    source_label=meta["source_label"],
                    source_note=meta["source_note"],
                    status_label=meta["status_label"],
                )
        else:
            st.markdown(grid_html, unsafe_allow_html=True)


def render_home_status_strip(items: list[dict]):
    pills = []
    for item in items:
        label = _safe_text(item.get("label"))
        value = _safe_text(item.get("value"))
        note = _safe_text(item.get("note"))
        tone = _safe_text(item.get("tone"), "need").strip().lower()
        tone_class = "home-status-pill"
        if tone in {"risk", "warning"}:
            tone_class += " home-status-pill-risk"
        elif tone == "draft":
            tone_class += " home-status-pill-draft"
        else:
            tone_class += " home-status-pill-need"
        pills.append(
            "<div class='"
            + tone_class
            + "'>"
            + f"<div class='home-status-label'>{escape(label)}</div>"
            + f"<div class='home-status-value'>{escape(value)}</div>"
            + f"<div class='home-status-note'>{escape(note)}</div>"
            + "</div>"
        )
    if pills:
        st.markdown(
            "<div class='home-status-strip'>" + "".join(pills) + "</div>",
            unsafe_allow_html=True,
        )


def render_home_quick_actions(
    actions: list[tuple[str, str]],
    *,
    queue_platform_route: Callable,
):
    if not actions:
        return
    st.markdown(
        "<div class='home-quick-nav-label'>Quick Actions</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='home-quick-action-note'>Jump straight into the next major workflow without opening the menu.</div>",
        unsafe_allow_html=True,
    )
    rows = [actions[idx : idx + 2] for idx in range(0, len(actions), 2)]
    for row_idx, row in enumerate(rows):
        columns = st.columns(2, gap="small")
        for col_idx, column in enumerate(columns):
            if col_idx >= len(row):
                continue
            label, route_key = row[col_idx]
            with column:
                if st.button(
                    label,
                    key=f"home_quick_action_{row_idx}_{route_key}",
                    use_container_width=True,
                    type="primary",
                ):
                    queue_platform_route(route_key)
                    st.rerun()
