"""Canonical Players and draft-pick exploration presentation."""

from __future__ import annotations

from html import escape
from typing import Callable

import pandas as pd
import streamlit as st

from modules import html_rendering
from modules import ui_primitives
from modules.player_asset_explorer_styles import PLAYER_ASSET_EXPLORER_CSS


AVAILABLE_PLAYERS_SCOPE = "Available Players"
ASSET_SCOPES = (
    "Players",
    AVAILABLE_PLAYERS_SCOPE,
    "Rookie picks",
    "Future picks",
    "All assets",
)
AGE_FILTERS = ("All ages", "Under 23", "23–25", "26–28", "29+")
STATUS_FILTERS = ("All statuses", "Active", "Injured", "Inactive")
AVAILABILITY_FILTERS = ("All availability", "Rostered", "Available")


def rostered_player_id_set(
    roster_player_map: dict[str, tuple[str, ...]] | None,
) -> set[str]:
    """One league-wide rostered id set — do not rebuild per row."""

    rostered: set[str] = set()
    for player_ids in (roster_player_map or {}).values():
        for player_id in player_ids or ():
            text = str(player_id).strip()
            if text:
                rostered.add(text)
    return rostered


def ownership_context_is_known(
    roster_player_map: dict[str, tuple[str, ...]] | None,
    *,
    ownership_known: bool | None = None,
) -> bool:
    if ownership_known is not None:
        return bool(ownership_known)
    return isinstance(roster_player_map, dict) and bool(roster_player_map)


def _text(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text or fallback


def ranked_player_frame(players: pd.DataFrame, score_field: str) -> pd.DataFrame:
    """Expose canonical overall rank while preserving value ordering.

    Never falls back to Sleeper ``search_rank`` as customer OVR — missing
    canonical ranks stay unavailable (NaN) rather than reusing market input.
    """

    if players is None or players.empty:
        return pd.DataFrame(columns=list(players.columns) if players is not None else [])
    ranked = players.copy()
    if "is_current_fantasy_eligible" in ranked.columns:
        ranked = ranked[
            ranked["is_current_fantasy_eligible"].fillna(False).astype(bool)
        ].copy()
    if ranked.empty:
        return ranked
    score_column = score_field if score_field in ranked.columns else "value_score"
    ranked["_explorer_score"] = pd.to_numeric(
        ranked.get(score_column, 0),
        errors="coerce",
    ).fillna(0)
    ranked = ranked.sort_values(
        "_explorer_score",
        ascending=False,
        kind="stable",
    )
    if "canonical_overall_rank" in ranked.columns:
        ranked["explorer_rank"] = pd.to_numeric(
            ranked["canonical_overall_rank"],
            errors="coerce",
        )
    elif "overall_rank" in ranked.columns and "rank_scoring_format" in ranked.columns:
        # Annotated league ranks only — not draft-local or FA-relative boards.
        ranked["explorer_rank"] = pd.to_numeric(
            ranked["overall_rank"],
            errors="coerce",
        )
    else:
        ranked["explorer_rank"] = pd.Series(
            pd.NA,
            index=ranked.index,
            dtype="Float64",
        )
    return ranked.drop(columns=["_explorer_score"])


def filter_player_results(
    players: pd.DataFrame,
    *,
    positions: tuple[str, ...] = (),
    age_filter: str = "All ages",
    status_filter: str = "All statuses",
    availability_filter: str = "All availability",
    rostered_player_ids: set[str] | None = None,
    is_injury_status: Callable | None = None,
) -> pd.DataFrame:
    """Apply UI-selected facets while preserving the incoming result order."""

    if players is None or players.empty:
        return players.copy() if players is not None else pd.DataFrame()
    filtered = players.copy()
    if positions:
        position_values = filtered.get(
            "position",
            pd.Series("", index=filtered.index),
        ).fillna("").astype(str).str.upper()
        filtered = filtered[position_values.isin(positions)]

    ages = pd.to_numeric(
        filtered.get("age", pd.Series(index=filtered.index, dtype="float64")),
        errors="coerce",
    )
    if age_filter == "Under 23":
        filtered = filtered[ages.lt(23)]
    elif age_filter == "23–25":
        filtered = filtered[ages.between(23, 25, inclusive="both")]
    elif age_filter == "26–28":
        filtered = filtered[ages.between(26, 28, inclusive="both")]
    elif age_filter == "29+":
        filtered = filtered[ages.ge(29)]

    if status_filter != "All statuses":
        injury_mask = (
            filtered.apply(is_injury_status, axis=1)
            if callable(is_injury_status)
            else pd.Series(False, index=filtered.index)
        )
        if status_filter == "Injured":
            status_mask = injury_mask
        else:
            status_values = filtered.get(
                "status",
                pd.Series("", index=filtered.index),
            ).fillna("").astype(str).str.casefold()
            if status_filter == "Active":
                status_mask = (
                    status_values.isin({"active", "healthy", ""})
                    & ~injury_mask
                )
            else:
                status_mask = (
                    ~status_values.isin({"active", "healthy", ""})
                    & ~injury_mask
                )
        filtered = filtered[status_mask]

    rostered = {str(player_id) for player_id in (rostered_player_ids or set())}
    if availability_filter != "All availability":
        player_ids = filtered.get(
            "player_id",
            pd.Series("", index=filtered.index),
        ).fillna("").astype(str)
        rostered_mask = player_ids.isin(rostered)
        filtered = filtered[
            rostered_mask if availability_filter == "Rostered" else ~rostered_mask
        ]
    return filtered


def filter_pick_results(
    picks: list[dict] | pd.DataFrame,
    *,
    asset_scope: str,
    current_draft_year: int | None,
) -> pd.DataFrame:
    frame = picks.copy() if isinstance(picks, pd.DataFrame) else pd.DataFrame(picks or [])
    if frame.empty:
        return frame
    frame["season"] = pd.to_numeric(frame.get("season"), errors="coerce")
    frame["round"] = pd.to_numeric(frame.get("round"), errors="coerce")
    if asset_scope == "Rookie picks" and current_draft_year:
        frame = frame[frame["season"].eq(current_draft_year)]
    elif asset_scope == "Future picks" and current_draft_year:
        frame = frame[frame["season"].gt(current_draft_year)]
    return frame


def pick_card_html(pick: dict, *, score_label: str) -> str:
    from modules import dense_list_primitives

    label = _text(pick.get("label"), "Draft pick")
    season = _text(pick.get("season"), "Future")
    round_value = _text(pick.get("round"), "—")
    value = _text(pick.get("score", pick.get("value_score")), "—")
    owner = _text(pick.get("owner_team_name"), "League asset")
    range_label = _text(pick.get("projected_pick_range") or pick.get("pick_tier"))
    identity = dense_list_primitives.dense_identity_html(
        primary=label,
        secondary=owner,
    )
    metric = dense_list_primitives.dense_metric_html(value, score_label)
    status = dense_list_primitives.dense_status_html("Draft pick", range_label)
    meta = dense_list_primitives.dense_meta_html(f"Season {season}", f"Round {round_value}")
    trail = dense_list_primitives.dense_trail_html(status_html=status, meta_html=meta)
    return dense_list_primitives.dense_row_html(
        identity_html=identity,
        metric_html=metric,
        trail_html=trail,
        density="compact",
        extra_classes=["explorer-pick-card", "dg-ui-card"],
        no_lead=True,
    )


def render_player_asset_explorer(
    *,
    df_players: pd.DataFrame,
    draft_picks: list[dict],
    roster_player_map: dict[str, tuple[str, ...]],
    score_field: str,
    score_label: str,
    search_assets: Callable,
    render_player_scan_cards: Callable,
    is_injury_status: Callable,
    pick_score_multiplier: float = 1.0,
    current_draft_year: int | None = None,
    ownership_known: bool | None = None,
) -> pd.DataFrame:
    """Render the explorer and return the visible player result frame."""

    # Lazy CSS — keep PLAYER_ASSET_EXPLORER_CSS off cold APP_CSS / protobuf path.
    html_rendering.inject_global_styles(PLAYER_ASSET_EXPLORER_CSS)
    ui_primitives.render_section_header(
        "Player & Asset Explorer",
        eyebrow="Market Search",
        subtitle=(
            "Find players and draft capital quickly, compare current context, "
            "then open Player Quick View for the deeper decision layer."
        ),
        heading_level=2,
    )
    query = st.text_input(
        "Search players and picks",
        key="player_asset_explorer_query",
        placeholder="Player, team, position, or pick shorthand (for example: 2027 1st)",
        autocomplete="off",
    )
    asset_scope = st.pills(
        "Asset type",
        ASSET_SCOPES,
        default="All assets",
        key="player_asset_explorer_scope",
    ) or "All assets"
    available_players_scope = asset_scope == AVAILABLE_PLAYERS_SCOPE
    roster_ownership_known = ownership_context_is_known(
        roster_player_map,
        ownership_known=ownership_known,
    )
    if available_players_scope:
        st.caption("Players currently unrostered in this league.")

    filter_count = 3 if available_players_scope else 4
    filter_columns = st.columns(filter_count)
    with filter_columns[0]:
        positions = tuple(
            st.multiselect(
                "Position",
                ["QB", "RB", "WR", "TE", "K"],
                key="player_asset_explorer_positions",
            )
        )
    with filter_columns[1]:
        age_filter = st.selectbox(
            "Age",
            AGE_FILTERS,
            key="player_asset_explorer_age",
        )
    with filter_columns[2]:
        status_filter = st.selectbox(
            "Status",
            STATUS_FILTERS,
            key="player_asset_explorer_status",
        )
    if available_players_scope:
        availability_filter = "Available"
    else:
        with filter_columns[3]:
            availability_filter = st.selectbox(
                "Availability",
                (
                    AVAILABILITY_FILTERS
                    if roster_ownership_known
                    else ("All availability",)
                ),
                key="player_asset_explorer_availability",
            )

    ranked = ranked_player_frame(df_players, score_field)
    rank_map: dict[str, int] = {}
    for _, row in ranked.iterrows():
        pid = _text(row.get("player_id"))
        if not pid:
            continue
        try:
            explorer_rank = int(row.get("explorer_rank"))
        except (TypeError, ValueError):
            continue
        if explorer_rank > 0:
            rank_map[pid] = explorer_rank

    current_year = current_draft_year
    if not current_year:
        pick_seasons = [
            int(value)
            for value in pd.to_numeric(
                pd.Series([pick.get("season") for pick in draft_picks or []]),
                errors="coerce",
            ).dropna()
        ]
        if pick_seasons:
            current_year = min(pick_seasons)

    include_players = asset_scope in {
        "Players",
        AVAILABLE_PLAYERS_SCOPE,
        "All assets",
    }
    include_picks = asset_scope in {"Rookie picks", "Future picks", "All assets"}
    rostered_ids = rostered_player_id_set(roster_player_map)
    if available_players_scope and not roster_ownership_known:
        ui_primitives.render_empty_state_panel(
            "League roster context unavailable",
            "Available Players needs a loaded league roster to know who is unrostered.",
            kind="unavailable",
            recovery_guidance="Load a supported league, then return to Player & Asset Explorer.",
        )
        return pd.DataFrame(columns=list(df_players.columns) if df_players is not None else [])

    searched = pd.DataFrame()
    if query.strip():
        searched = search_assets(
            df_players,
            draft_picks,
            query,
            score_field=score_field,
            pick_score_multiplier=pick_score_multiplier,
            asset_filter=(
                "Players"
                if asset_scope in {"Players", AVAILABLE_PLAYERS_SCOPE}
                else "Picks"
                if asset_scope in {"Rookie picks", "Future picks"}
                else "All"
            ),
            limit=60,
        )

    if query.strip():
        player_results = (
            searched[searched.get("asset_type", "").eq("player")].copy()
            if not searched.empty and "asset_type" in searched.columns
            else pd.DataFrame()
        )
        pick_results = (
            searched[searched.get("asset_type", "").eq("pick")].copy()
            if not searched.empty and "asset_type" in searched.columns
            else pd.DataFrame()
        )
    else:
        player_results = ranked.copy() if include_players else pd.DataFrame()
        pick_results = (
            filter_pick_results(
                draft_picks,
                asset_scope=asset_scope,
                current_draft_year=current_year,
            )
            if include_picks
            else pd.DataFrame()
        )

    if not player_results.empty:
        player_results["explorer_rank"] = (
            player_results.get(
                "player_id",
                pd.Series("", index=player_results.index),
            )
            .fillna("")
            .astype(str)
            .map(rank_map)
        )
    player_results = filter_player_results(
        player_results,
        positions=positions,
        age_filter=age_filter,
        status_filter=status_filter,
        availability_filter=availability_filter,
        rostered_player_ids=rostered_ids,
        is_injury_status=is_injury_status,
    )
    if include_picks:
        pick_results = filter_pick_results(
            pick_results,
            asset_scope=asset_scope,
            current_draft_year=current_year,
        )
    else:
        pick_results = pd.DataFrame()

    result_count = len(player_results) + len(pick_results)
    st.caption(
        f"{result_count} matching asset{'s' if result_count != 1 else ''}. "
        "Results keep the existing search and value ordering."
    )
    if result_count == 0:
        if query.strip():
            ui_primitives.render_empty_state_panel(
                "No matching assets",
                "No players or supported picks match this search and filter combination.",
                kind="filtered-empty",
                recovery_guidance="Check the spelling, remove a filter, or try pick shorthand such as 2027 1st.",
            )
        elif available_players_scope:
            ui_primitives.render_empty_state_panel(
                "No available players",
                "Every matching player is currently rostered in this league, or filters removed the rest.",
                kind="filtered-empty",
                recovery_guidance="Clear position, age, or status filters, or switch Asset type to Players.",
            )
        elif include_picks and not draft_picks:
            ui_primitives.render_empty_state_panel(
                "Draft-pick data unavailable",
                "No supported rookie or future-pick assets are available for the active league.",
                kind="unavailable",
                recovery_guidance="Load a supported league to explore its draft capital.",
            )
        else:
            ui_primitives.render_empty_state_panel(
                "No players match these filters",
                "The current position, age, status, and availability filters remove every player.",
                kind="filtered-empty",
                recovery_guidance="Clear one or more filters to restore the player board.",
            )
        return player_results

    if not player_results.empty:
        ui_primitives.render_section_header(
            "Players",
            eyebrow="Ranked Results",
            subtitle="Dynasty value, rank, and current context in one scan.",
            heading_level=3,
        )

        def player_context(row) -> str:
            from modules import canonical_player_ranking

            compact = canonical_player_ranking.format_compact_rank(
                row.get("canonical_overall_rank", row.get("overall_rank")),
                row.get("canonical_position_rank", row.get("position_rank")),
                row.get("position"),
                unavailable_reason=row.get("rank_unavailable_reason"),
            )
            context = _text(
                row.get("opportunity_label")
                or row.get("status")
                or row.get("player_tier"),
                "Current context unavailable",
            )
            return f"{compact} · {context}"

        render_player_scan_cards(
            player_results,
            score_field=score_field,
            title="Player results",
            note="Open any result for Player Quick View.",
            max_items=20,
            compact=True,
            enable_quick_view=True,
            quick_view_source_label="Player & Asset Explorer",
            quick_view_key_prefix="player_asset_explorer",
            note_fn=player_context,
            show_inline_reason=True,
            show_header=False,
            design_system=True,
        )

    if not pick_results.empty:
        ui_primitives.render_section_header(
            "Draft Picks",
            eyebrow="League Assets",
            subtitle="Current values and ownership context; pick valuation is unchanged.",
            heading_level=3,
        )
        st.markdown(
            "<div class='explorer-pick-grid'>"
            + "".join(
                pick_card_html(row.to_dict(), score_label=score_label)
                for _, row in pick_results.head(8).iterrows()
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    return player_results
