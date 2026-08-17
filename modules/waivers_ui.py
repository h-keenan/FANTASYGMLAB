from html import escape
from typing import Callable

import pandas as pd
import streamlit as st

from modules import canonical_recommendation_narrative
from modules import deferred_rendering
from modules import runtime_trace
from modules import league_workspace_ui
from modules import football_assets, ui_primitives
from modules.player_cards import (
    injury_adjusted_value_html,
    player_prestige_level,
)
from modules.player_tier_identity import resolve_player_tier_identity
from modules import player_profile_ui
from modules.faab import format_faab_block_html, recommend_faab_guidance


WAIVERS_DETAILED_TABLE_PREVIEW_ROWS = 40

_safe_text = league_workspace_ui._safe_text
_safe_positive_int = league_workspace_ui._safe_positive_int
_format_score = league_workspace_ui._format_score
_format_age = league_workspace_ui._format_age
league_score_label = league_workspace_ui.league_score_label


def waiver_section_header_html(title: str, *, kicker: str, note: str, preset: str = "secondary") -> str:
    return (
        f"<div class='waiver-section-header dg-section-{escape(preset)}'>"
        + ui_primitives.section_header_html(
            title,
            eyebrow=kicker,
            subtitle=note,
            heading_level=2,
        )
        + "</div>"
    )


def _compact_text(value: object, limit: int = 150) -> str:
    text = " ".join(_safe_text(value).split())
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip(" ,;:-") + "..."


def _session_faab_remaining() -> int | None:
    raw = st.session_state.get("faab_remaining_budget")
    if raw in (None, ""):
        return None
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return None


def _session_faab_min_bid() -> int:
    raw = st.session_state.get("faab_min_bid")
    if raw in (None, ""):
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def waiver_faab_guidance_for_row(
    row,
    *,
    score_field: str,
    needed_positions: list[str] | None = None,
    is_starter: bool = False,
):
    settings = st.session_state.get("league_value_settings")
    if not isinstance(settings, dict):
        settings = {}
    try:
        score = int(float(row.get(score_field, row.get("value_score", 0)) or 0))
    except (TypeError, ValueError):
        score = 0
    position = _safe_text(row.get("position")).upper()
    needed = {str(pos).upper() for pos in (needed_positions or []) if str(pos).upper()}
    remaining = _session_faab_remaining()
    return recommend_faab_guidance(
        player_score=score,
        position=position,
        is_starter=is_starter,
        budget=remaining if remaining is not None else 100,
        league_settings=settings,
        status=_safe_text(row.get("status")),
        injury_status=_safe_text(row.get("injury_status")),
        injury_need_match=bool(row.get("injury_replacement_fit")),
        remaining_budget=remaining,
        min_bid=_session_faab_min_bid(),
        team_strategy=_safe_text(settings.get("team_strategy")),
        week=settings.get("week"),
        roster_need=position in needed,
        confidence=_safe_text(row.get("opportunity_confidence")),
        available=not bool(row.get("stale_free_agent")),
    )


def waiver_recommendation_label(row, position_rank: int) -> tuple[str, str]:
    """Translate existing waiver signals into a concise presentation label."""

    if bool(row.get("stale_free_agent")):
        return "Watch", "neutral"
    if bool(row.get("injury_replacement_fit")) or position_rank <= 3:
        return "Add", "opportunity"
    opportunity = _safe_text(row.get("opportunity_label")).strip()
    try:
        age = float(row.get("age") or 0)
    except Exception:
        age = 0
    if (age and age <= 24) or opportunity in {
        "Backup With Upside",
        "Starter At Risk",
        "Committee Back",
    }:
        return "Stash", "information"
    return "Watch", "neutral"


def select_top_waiver_opportunity(
    free_agents: pd.DataFrame,
    roster_df: pd.DataFrame,
    league_settings: dict | None,
    score_field: str,
    *,
    needed_positions: list[str] | None = None,
):
    if free_agents is None or free_agents.empty:
        return pd.Series(dtype="object")

    ranked = rank_priority_add_candidates(
        free_agents,
        score_field=score_field,
        needed_positions=needed_positions or [],
        league_settings=league_settings or {},
        roster_df=roster_df if roster_df is not None else pd.DataFrame(),
        max_items=1,
    )
    if ranked.empty:
        return pd.Series(dtype="object")
    selected = ranked.iloc[0].copy()
    kicker_required = int((league_settings or {}).get("k_count") or 0) > 0
    if (
        str(selected.get("position") or "").strip().upper() == "K"
        and kicker_required
        and bool(selected.get("priority_need_fit"))
    ):
        selected["kicker_need_fit"] = True
        selected["injury_replacement_note"] = (
            "Your lineup requires a kicker and the roster does not currently "
            "have a viable active option."
        )
    return selected


def _roster_has_viable_kicker(roster_df: pd.DataFrame) -> bool:
    if roster_df is None or roster_df.empty:
        return False
    positions = (
        roster_df.get("position", pd.Series(dtype="object"))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    kicker_rows = roster_df[positions.eq("K")].copy()
    if kicker_rows.empty:
        return False
    team_values = kicker_rows.get(
        "team",
        pd.Series("", index=kicker_rows.index),
    ).fillna("").astype(str).str.strip().str.upper()
    status_values = (
        kicker_rows.get(
            "status",
            pd.Series("", index=kicker_rows.index),
        ).fillna("").astype(str).str.strip().str.lower()
        + " "
        + kicker_rows.get(
            "injury_status",
            pd.Series("", index=kicker_rows.index),
        ).fillna("").astype(str).str.strip().str.lower()
    )
    unavailable = status_values.str.contains(
        r"\b(?:ir|out|inactive|suspended|pup|nfi)\b",
        regex=True,
    )
    return bool(
        (
            team_values.ne("")
            & ~team_values.isin({"FA", "FREE AGENT", "NONE", "N/A"})
            & ~unavailable
        ).any()
    )


def _qb_format(league_settings: dict | None) -> str:
    settings = league_settings or {}
    raw = str(settings.get("qb_format") or "").strip().casefold()
    if "super" in raw or raw in {"sf", "superflex"}:
        return "superflex"
    if "2qb" in raw or raw == "2":
        return "2qb"
    if int(settings.get("superflex_count") or 0) > 0:
        return "superflex"
    return "1qb"


def _score_series(frame: pd.DataFrame, score_field: str) -> pd.Series:
    return pd.to_numeric(frame.get(score_field, 0), errors="coerce").fillna(0.0)


def rank_priority_add_candidates(
    free_agents: pd.DataFrame,
    *,
    score_field: str,
    needed_positions: list[str] | None,
    league_settings: dict | None,
    roster_df: pd.DataFrame | None,
    max_items: int = 6,
) -> pd.DataFrame:
    """Order Priority Adds for THIS roster — not bare dynasty-score tops.

    Preserves Best Available as a separate Snapshot surface. Uses existing
    TeamNeedsAssessment outputs + score/injury flags. Does not invent a new
    opaque score.
    """

    if free_agents is None or free_agents.empty or max_items <= 0:
        return free_agents.iloc[0:0].copy() if free_agents is not None else pd.DataFrame()

    candidates = free_agents.copy()
    settings = league_settings or {}
    needed = {
        str(pos).upper()
        for pos in (needed_positions or [])
        if str(pos).upper()
    }
    positions = (
        candidates.get("position", pd.Series("", index=candidates.index))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    scores = _score_series(candidates, score_field)
    stale = candidates.get(
        "stale_free_agent",
        pd.Series(False, index=candidates.index, dtype="bool"),
    ).fillna(False)
    injury_fit = candidates.get(
        "injury_replacement_fit",
        pd.Series(False, index=candidates.index, dtype="bool"),
    ).fillna(False)

    kicker_required = int(settings.get("k_count") or 0) > 0
    has_viable_kicker = _roster_has_viable_kicker(
        roster_df if roster_df is not None else pd.DataFrame()
    )
    suppress_kickers = not (kicker_required and not has_viable_kicker)
    qb_format = _qb_format(settings)

    positive = candidates[(~stale) & (scores > 0)].copy()
    if positive.empty:
        return candidates.iloc[0:0].copy()

    pos_scores = _score_series(positive, score_field)
    # Exceptional wire value: top overall FA or clearly above the featured pack.
    top_cutoff = float(pos_scores.quantile(0.85)) if len(pos_scores) >= 4 else float(pos_scores.max())
    overall_rank = pos_scores.rank(ascending=False, method="first")

    need_fit = []
    value_opportunity = []
    actionable = []
    skill_needs = needed - {"QB", "TE", "K"}
    for idx in positive.index:
        position = str(positive.at[idx, "position"] or "").upper()
        score = float(pos_scores.at[idx])
        injured = bool(injury_fit.at[idx] if idx in injury_fit.index else False)
        is_need = position in needed or injured
        if position == "K":
            is_need = bool(kicker_required and not has_viable_kicker)
        is_elite_value = bool(overall_rank.at[idx] <= 2 or score >= top_cutoff)
        if position in {"QB", "TE"} and position not in needed and not injured:
            is_need = False
            # Do not let covered QB/TE displace true skill-position needs.
            if skill_needs:
                is_elite_value = False
            elif position == "QB" and qb_format == "1qb":
                # Adequate 1QB rooms: ordinary QBs are not Priority Adds.
                is_elite_value = False
            elif position == "TE":
                is_elite_value = bool(overall_rank.at[idx] <= 1 and score >= top_cutoff)
            else:
                # Superflex without a true QB need: only exceptional wire QB value.
                is_elite_value = bool(overall_rank.at[idx] <= 2 and score >= top_cutoff)
        if position == "K" and suppress_kickers:
            is_need = False
            is_elite_value = False
        need_fit.append(is_need)
        value_opportunity.append(bool(is_elite_value and not is_need))
        actionable.append(bool(is_need or is_elite_value))

    positive = positive.copy()
    positive["priority_need_fit"] = need_fit
    positive["priority_value_opportunity"] = value_opportunity
    positive["priority_actionable"] = actionable
    positive["_priority_score"] = pos_scores
    positive["_injury_fit"] = injury_fit.reindex(positive.index).fillna(False)
    positive = positive[positive["priority_actionable"]].copy()
    if positive.empty:
        return positive

    positive = positive.sort_values(
        ["_injury_fit", "priority_need_fit", "priority_value_opportunity", "_priority_score"],
        ascending=[False, False, False, False],
    )

    # Soft diversity: prefer decision utility across rooms without a rigid 1-of-each rule.
    selected_indices: list = []
    position_counts: dict[str, int] = {}
    soft_cap = 2
    for idx, row in positive.iterrows():
        position = str(row.get("position") or "").upper()
        count = position_counts.get(position, 0)
        exceptional = bool(row.get("priority_need_fit")) or bool(row.get("_injury_fit"))
        if count >= soft_cap and not (
            exceptional and count < soft_cap + 1 and qb_format != "1qb" and position == "QB"
        ):
            # Allow a third same-position pick only for true need/injury, and never
            # flood 1QB boards with ordinary QBs (already demoted above).
            if count >= soft_cap and not (exceptional and position != "QB"):
                if count >= soft_cap + 1:
                    continue
                if position == "QB" and qb_format == "1qb":
                    continue
                if not exceptional:
                    continue
        selected_indices.append(idx)
        position_counts[position] = count + 1
        if len(selected_indices) >= max_items:
            break

    if len(selected_indices) < max_items:
        for idx in positive.index:
            if idx in selected_indices:
                continue
            selected_indices.append(idx)
            if len(selected_indices) >= max_items:
                break

    result = positive.loc[selected_indices].copy()
    drop_cols = [col for col in ("_priority_score", "_injury_fit") if col in result.columns]
    if drop_cols:
        result = result.drop(columns=drop_cols)
    return result.reset_index(drop=True)


def free_agent_priority_badge(
    row,
    position_rank: int,
) -> tuple[str, str]:
    stale = bool(row.get("stale_free_agent"))
    try:
        score = int(
            round(
                float(
                    row.get(
                        "score",
                        row.get("value_score", 0),
                    )
                    or 0
                )
            )
        )
    except Exception:
        score = 0
    if stale or score <= 0:
        return "Deprioritized", "free-agent-tag free-agent-tag-muted"
    if position_rank <= 1:
        return "Best Available", "free-agent-tag free-agent-tag-emphasis"
    if position_rank <= 3:
        return "Priority Add", "free-agent-tag free-agent-tag-emphasis"
    if position_rank <= 8:
        return "Depth Add", "free-agent-tag"
    return "Watch List", "free-agent-tag"


def free_agent_reason_text(
    row,
    position_rank: int,
    score_label: str,
    needed_positions: list[str] | None = None,
    *,
    recommendation_reason_text: Callable,
) -> str:
    position = _safe_text(row.get("position"), "Player").upper()
    stale = bool(row.get("stale_free_agent"))
    needed_set = {
        str(pos).upper()
        for pos in (needed_positions or [])
        if str(pos).upper()
    }
    need_match = position in needed_set or bool(row.get("priority_need_fit"))
    value_opportunity = bool(row.get("priority_value_opportunity"))
    try:
        score = int(
            round(
                float(
                    row.get(
                        "score",
                        row.get("value_score", 0),
                    )
                    or 0
                )
            )
        )
    except Exception:
        score = 0
    try:
        age = float(row.get("age") or 0)
    except Exception:
        age = 0

    if bool(row.get("injury_replacement_fit")):
        injury_note = _safe_text(
            row.get("injury_replacement_note"),
            f"Healthy injury replacement at {position} for a starter spot your roster is already sweating.",
        )
        if need_match:
            return (
                f"{injury_note} It also matches one of your current roster needs."
            )
        return injury_note
    if bool(row.get("kicker_need_fit")):
        return _safe_text(
            row.get("injury_replacement_note"),
            "Your lineup requires a kicker and the roster does not currently have a viable active option.",
        )
    opportunity_label = _safe_text(row.get("opportunity_label"))
    opportunity_explanation = _safe_text(
        row.get("opportunity_explanation")
    )
    if stale or score <= 0:
        return (
            "Shown for completeness, but this profile looks stale or low-value "
            "under the current lens so it is not a priority add."
        )
    if value_opportunity and not need_match:
        if opportunity_explanation:
            return (
                "Dynasty value opportunity even without a primary positional need. "
                f"{recommendation_reason_text(opportunity_explanation, 110)}"
            )
        return (
            f"Dynasty value opportunity on the wire under the current "
            f"{score_label.lower()} lens — worth considering despite roster depth."
        )
    if need_match and opportunity_explanation:
        return (
            f"Matches your {position} need right now. "
            f"{recommendation_reason_text(opportunity_explanation, 120)}"
        )
    if (
        opportunity_explanation
        and opportunity_label
        in {
            "Elite Opportunity",
            "Strong Opportunity",
            "Committee Back",
            "Starter At Risk",
            "Backup With Upside",
            "Handcuff",
        }
    ):
        return opportunity_explanation
    if position_rank == 1:
        if need_match:
            return (
                f"Top available {position} on this wire and it directly patches "
                "one of your thinnest roster rooms."
            )
        if opportunity_label:
            return (
                f"Top available {position} on this wire under the current "
                f"{score_label.lower()} lens. Opportunity: "
                f"{opportunity_label.lower()}."
            )
        return (
            f"Top available {position} on this wire under the current "
            f"{score_label.lower()} lens."
        )
    if need_match:
        return (
            f"Matches your current {position} need and gives you a low-cost way "
            "to patch that room."
        )
    if age and age <= 24:
        return (
            f"Younger {position} stash if you want upside without paying trade "
            "value."
        )
    if position == "QB":
        return (
            "Useful depth or matchup-based quarterback option if your room is "
            "thin."
        )
    if position == "RB":
        return (
            "Worth considering when you need quick bench depth or "
            "injury-contingency help."
        )
    if position == "WR":
        return (
            "Reasonable receiver depth add for bye weeks, flex coverage, or "
            "bench insulation."
        )
    if position == "TE":
        return (
            "Playable tight end depth if your lineup needs a second viable "
            "option."
        )
    if position == "K":
        return "Viable kicker stream if your league still starts the position."
    return "Available depth piece under the current scoring lens."


def render_free_agent_summary_cards(
    free_agents: pd.DataFrame,
    score_field: str,
    *,
    player_display_name: Callable,
    cached_headshot_data_url: Callable | None = None,
    asset_initials: Callable | None = None,
    render_tappable_player_html: Callable | None = None,
    open_player_quick_view: Callable | None = None,
    key_prefix: str = "waiver_summary",
):
    if free_agents.empty:
        return

    score_label = league_score_label(score_field)
    stale_series = (
        free_agents["stale_free_agent"].fillna(False)
        if "stale_free_agent" in free_agents.columns
        else pd.Series(False, index=free_agents.index, dtype="bool")
    )
    active_agents = free_agents[
        (~stale_series)
        & (
            pd.to_numeric(
                free_agents.get(score_field, 0),
                errors="coerce",
            ).fillna(0)
            > 0
        )
    ].copy()
    source_df = active_agents if not active_agents.empty else free_agents.copy()

    cards = []
    quick_view_meta: dict[str, dict[str, str]] = {}
    for position in ["QB", "RB", "WR", "TE", "K"]:
        group = source_df[source_df["position"] == position].copy()
        if group.empty:
            continue
        group = group.sort_values(score_field, ascending=False)
        top_row = group.iloc[0]
        player_id = _safe_text(top_row.get("player_id")).strip()
        score = _format_score(
            top_row.get(
                score_field,
                top_row.get("value_score", 0),
            )
        )
        count = len(group)
        age = _format_age(top_row.get("age"))
        image_url = (
            cached_headshot_data_url(player_id)
            if player_id and cached_headshot_data_url is not None
            else ""
        )
        fantasy_ppg = next(
            (
                player_profile_ui.format_player_stat_value(top_row.get(field), "ppg")
                for field in ("fantasy_ppg", "ppr_ppg", "ppg")
                if _safe_text(top_row.get(field)).strip()
            ),
            "",
        )
        cards.append(
            football_assets.player_card_html(
                football_assets.FootballPlayerAsset(
                    player_id=player_id,
                    display_name=player_display_name(top_row),
                    position=position,
                    team=_safe_text(top_row.get("team"), "FA"),
                    prestige_label="Best Available",
                    prestige_level="contributor",
                    value_label=score_label,
                    value=score,
                    insight=(
                        f"{fantasy_ppg} PPG · {count} active options"
                        if fantasy_ppg
                        else f"{count} active options"
                    ),
                    age=f"Age {age}" if age else "",
                ),
                density="compact",
                mode="action-enabled" if player_id else "read-only",
                identity=resolve_player_tier_identity(top_row),
                avatar_html=player_profile_ui.avatar_html(
                    image_url,
                    (
                        asset_initials(player_display_name(top_row))
                        if asset_initials is not None
                        else player_display_name(top_row)[:1]
                    ),
                    css_class="waiver-snapshot-avatar",
                ),
                extra_classes=("free-agent-summary-card", "dg-card-secondary"),
                stacked=True,
            )
        )
        if player_id:
            quick_view_meta[player_id] = {
                "source_label": "Waivers - Wire Snapshot",
                "source_note": f"Top available {position} on the current wire.",
                "status_label": "Best Available",
            }

    if cards:
        grid_html = (
            "<div class='free-agent-summary-grid'>"
            + "".join(cards)
            + "</div>"
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


def render_free_agent_cards(
    free_agents: pd.DataFrame,
    score_field: str,
    max_items: int = 12,
    needed_positions: list[str] | None = None,
    key_prefix: str = "waiver",
    *,
    recommendation_reason_text: Callable,
    player_display_name: Callable,
    cached_headshot_data_url: Callable,
    asset_initials: Callable,
    player_status_style: Callable,
    canonical_player_status: Callable,
    tier_chip_html: Callable,
    player_support_chip_html: Callable,
    player_status_pill_html: Callable,
    render_tappable_player_html: Callable,
    open_player_quick_view: Callable,
    render_recommendation_feedback: Callable,
):
    if free_agents.empty:
        ui_primitives.render_empty_state_panel(
            "No waiver targets available",
            "No active free agents currently match this waiver section.",
            kind="no-data",
            recovery_guidance="Check the selected league and current filters, then refresh the league when new players become available.",
        )
        return

    score_label = league_score_label(score_field)
    df = free_agents.copy().head(max_items).reset_index(drop=True)
    feedback_rows = []
    for index, row in df.iterrows():
        position = _safe_text(row.get("position"), "Player").upper()
        team = _safe_text(row.get("team")).strip() or "FA"
        age = _format_age(row.get("age"))
        score = _format_score(
            row.get(
                score_field,
                row.get("value_score", 0),
            )
        )
        player_id = _safe_text(row.get("player_id"))
        badge_text, _badge_class = free_agent_priority_badge(
            row,
            _safe_positive_int(row.get("position_rank"), 99),
        )
        image_url = (
            cached_headshot_data_url(player_id) if player_id else ""
        )

        primary_status = badge_text
        status_style = player_status_style(primary_status)
        tags: list[str] = []
        tier_label = _safe_text(row.get("player_tier")).strip()
        if (
            tier_label
            and canonical_player_status(tier_label).lower()
            != status_style["label"].lower()
        ):
            tags.append(tier_chip_html(tier_label))
        position_rank = _safe_positive_int(
            row.get("position_rank"),
            0,
        )
        opportunity_label = _safe_text(
            row.get("opportunity_label")
        ).strip()
        if opportunity_label in {
            "Elite Opportunity",
            "Strong Opportunity",
            "Backup With Upside",
        }:
            tags.append(
                player_support_chip_html(opportunity_label, "success")
            )
        elif opportunity_label == "Starter At Risk":
            tags.append(
                player_support_chip_html(opportunity_label, "warning")
            )
        try:
            age_value = float(row.get("age") or 0)
        except Exception:
            age_value = 0
        if (
            age_value
            and age_value <= 24
            and not bool(row.get("stale_free_agent"))
            and len(tags) < 3
        ):
            tags.append(player_support_chip_html("Young Stash", "hold"))
        if (
            bool(row.get("injury_replacement_fit"))
            and primary_status != "Injury Replacement"
            and len(tags) < 3
        ):
            tags.append(
                player_support_chip_html(
                    "Injury Replacement",
                    "warning",
                )
            )
        from modules import canonical_player_ranking

        canonical_chip = canonical_player_ranking.format_compact_rank(
            row.get("canonical_overall_rank"),
            row.get("canonical_position_rank"),
            position,
            unavailable_reason=row.get("rank_unavailable_reason"),
        )
        if canonical_chip != "Rank unavailable" and len(tags) < 3:
            tags.append(player_support_chip_html(canonical_chip, "neutral"))
        elif position_rank > 0 and len(tags) < 3:
            tags.append(
                player_support_chip_html(
                    f"Wire {position} #{position_rank}",
                    "neutral",
                )
            )

        reason_text = free_agent_reason_text(
            row,
            position_rank or 99,
            score_label,
            needed_positions=needed_positions,
            recommendation_reason_text=recommendation_reason_text,
        )
        recommendation_label, recommendation_variant = waiver_recommendation_label(
            row,
            position_rank or 99,
        )
        confidence = _safe_text(row.get("opportunity_confidence")).strip()
        urgency = {
            "Add": "Act now",
            "Stash": "Consider",
            "Watch": "Monitor",
        }[recommendation_label]
        recommendation_badge = ui_primitives.status_badge_html(
            recommendation_label,
            variant=recommendation_variant,
        )
        faab_guidance = waiver_faab_guidance_for_row(
            row,
            score_field=score_field,
            needed_positions=needed_positions,
            is_starter=recommendation_label == "Add",
        )
        faab_html = format_faab_block_html(faab_guidance)
        card_classes = ["free-agent-card", "dg-ui-card", "dg-ui-card--elevated"]
        if bool(row.get("stale_free_agent")):
            card_classes.append("dg-card-reference")
        elif bool(row.get("injury_replacement_fit")) or position_rank <= 3:
            card_classes.append("dg-card-primary")
        else:
            card_classes.append("dg-card-secondary")
        card_classes.append(
            f"free-agent-card-tone-{status_style['tone']}"
        )
        details_html = (
            "<div class='waiver-recommendation-row'>"
            + recommendation_badge
            + "</div>"
            + faab_html
            + "<div class='waiver-decision-summary'>"
            + f"<p class='waiver-decision-why'>{escape(_compact_text(reason_text, 128))}</p>"
            + "</div>"
            + "<div class='waiver-compact-metrics'>"
            + (f"<span>{escape(confidence)} confidence</span>" if confidence else "")
            + f"<span>{escape(urgency)}</span>"
            + (f"<span>Wire {escape(position)} #{position_rank}</span>" if position_rank else "")
            + "</div>"
            + "<div class='waiver-card-action' aria-hidden='true'>Review add →</div>"
        )
        card_html = football_assets.player_card_html(
            football_assets.FootballPlayerAsset(
                player_id=player_id,
                display_name=player_display_name(row),
                position=position,
                team=team,
                prestige_label=status_style["label"],
                prestige_level=player_prestige_level(status_style["label"]),
                status="",
                value_label=score_label,
                value=score,
                age=f"Age {age}" if age else "",
            ),
            density="standard",
            mode="action-enabled" if player_id else "read-only",
            identity=resolve_player_tier_identity(row),
            avatar_html=player_profile_ui.avatar_html(
                image_url,
                asset_initials(_safe_text(row.get("name"), "Player")),
                css_class=(
                    "free-agent-avatar "
                    f"avatar-tone-{status_style['tone']}"
                ),
            ),
            tags_html=(
                f"<span class='free-agent-tags'>{''.join(tags[:2])}</span>" if tags else ""
            ),
            value_html=injury_adjusted_value_html(
                score_label,
                score,
                row,
                css_class="free-agent-score-pill",
            ),
            details_html=details_html,
            extra_classes=tuple(card_classes),
            stacked=True,
        )
        clicked_player_id = render_tappable_player_html(
            html=card_html,
            key_prefix=(
                f"{_safe_text(key_prefix, 'waiver')}_profile_"
                f"{player_id}_{index}"
            ),
        )
        if clicked_player_id == player_id and player_id:
            waiver_narrative = canonical_recommendation_narrative.build_waiver_narrative(
                row,
                action=recommendation_label,
                reason=reason_text,
                league_id=_safe_text(st.session_state.get("selected_league_id")),
                roster_id=_safe_text(st.session_state.get("my_roster_id")),
                valuation_lens=_safe_text(score_field),
                source_surface="waivers",
            )
            open_player_quick_view(
                player_id,
                source_label="Waivers",
                source_note=waiver_narrative.shorten("reason", 160),
                status_label=recommendation_label,
                recommendation_narrative=waiver_narrative.to_dict(),
            )
        try:
            from modules import share_recommendation_cards as share_cards
            from modules import share_recommendation_ui

            if share_cards.experiment_enabled() and int(index) < 3:
                overall_rank = row.get("canonical_overall_rank")
                try:
                    overall_rank_i = int(overall_rank) if overall_rank not in (None, "") else None
                except (TypeError, ValueError):
                    overall_rank_i = None
                share_card = share_cards.build_waiver_share_card(
                    row,
                    action=recommendation_label,
                    reason=reason_text,
                    position_rank=position_rank or None,
                    overall_rank=overall_rank_i,
                    source_surface="waivers",
                    faab_label=faab_guidance.as_label(),
                    value_label=f"{score_label} {score}".strip(),
                )
                share_recommendation_ui.render_share_controls(
                    share_card,
                    key=f"{_safe_text(key_prefix, 'waiver')}_share_{player_id}_{index}",
                    state=st.session_state,
                )
        except Exception:
            pass
        if int(index) < 5:
            feedback_rows.append(
                {
                    "player_id": player_id,
                    "player_name": player_display_name(row),
                    "value_score": row.get(
                        score_field,
                        row.get("value_score"),
                    ),
                    "opportunity_score": row.get("opportunity_score"),
                    "position_rank": position_rank,
                    "opportunity_confidence": row.get(
                        "opportunity_confidence"
                    ),
                    "priority_label": badge_text,
                    "opportunity_label": opportunity_label,
                    "reason": reason_text,
                }
            )
    if feedback_rows:
        render_recommendation_feedback(
            page="waivers",
            surface="Waiver Recommendations",
            recommendation_type="waiver_add",
            key_prefix=f"{_safe_text(key_prefix, 'waiver')}_feedback",
            recommendation_title="Waiver recommendation board",
            recommendation_summary="Report a waiver recommendation that looks wrong.",
            player_ids=[item["player_id"] for item in feedback_rows],
            player_names=[item["player_name"] for item in feedback_rows],
            score_fields={
                "candidates": [
                    {
                        "player_id": item["player_id"],
                        "value_score": item["value_score"],
                        "opportunity_score": item["opportunity_score"],
                        "position_rank": item["position_rank"],
                    }
                    for item in feedback_rows
                ]
            },
            confidence_fields={
                "candidate_confidence": {
                    item["player_id"]: item["opportunity_confidence"]
                    for item in feedback_rows
                }
            },
            reason_fields={
                "candidate_reasons": {
                    item["player_id"]: {
                        "priority_label": item["priority_label"],
                        "opportunity_label": item["opportunity_label"],
                        "reason": item["reason"],
                    }
                    for item in feedback_rows
                }
            },
        )


def _dedupe_waiver_sections(
    featured: pd.DataFrame,
    stash: pd.DataFrame,
    watchlist: pd.DataFrame,
    faab: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Prevent the same player from appearing in multiple waiver sections."""

    seen: set[str] = set()
    if featured is not None and not featured.empty and "player_id" in featured.columns:
        seen.update(featured["player_id"].astype(str).tolist())

    def _exclude_seen(frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty or "player_id" not in frame.columns:
            return frame.iloc[0:0].copy() if frame is not None else pd.DataFrame()
        filtered = frame[~frame["player_id"].astype(str).isin(seen)].copy()
        seen.update(filtered["player_id"].astype(str).tolist())
        return filtered

    return featured, _exclude_seen(stash), _exclude_seen(watchlist), _exclude_seen(faab)


@runtime_trace.traced("waiver_generation", phase="waiver_generation")
def render_waiver_workspace_sections(
    *,
    free_agents_ranked: pd.DataFrame,
    featured_free_agents: pd.DataFrame,
    stash_candidates: pd.DataFrame,
    watchlist_candidates: pd.DataFrame,
    faab_targets: pd.DataFrame,
    df_free_display: pd.DataFrame,
    waiver_display_cols: list[str],
    score_field: str,
    selected_league_id: str,
    needed_positions: list[str],
    injury_positions: set[str],
    injured_starters: int,
    render_free_agent_summary_cards: Callable,
    render_free_agent_cards: Callable,
    add_injury_markers: Callable,
    format_score_columns: Callable,
    is_premium: bool = True,
    render_premium_lock: Callable | None = None,
    priority_adds: pd.DataFrame | None = None,
    render_guest_continuity: Callable | None = None,
) -> None:
    priority_board = (
        priority_adds
        if priority_adds is not None
        else featured_free_agents.head(6)
    )
    _, stash_candidates, watchlist_candidates, faab_targets = _dedupe_waiver_sections(
        priority_board if not priority_board.empty else featured_free_agents.head(6),
        stash_candidates,
        watchlist_candidates,
        faab_targets,
    )
    st.markdown(
        waiver_section_header_html(
            "Waiver Snapshot",
            kicker="Wire Status",
            note="Best available options by position — broad wire scan, not roster priorities.",
            preset="metrics",
        ),
        unsafe_allow_html=True,
    )
    render_free_agent_summary_cards(free_agents_ranked, score_field)

    st.markdown(
        waiver_section_header_html(
            "Priority Adds",
            kicker="Next Add",
            note=(
                "Adds most relevant to improving your roster — need fits first, "
                f"then exceptional {league_score_label(score_field).lower()} opportunities."
            ),
            preset="opportunity-list",
        ),
        unsafe_allow_html=True,
    )
    if injury_positions:
        highlighted_positions = " / ".join(sorted(injury_positions))
        st.caption(
            f"Injury replacement watch is active for "
            f"{highlighted_positions}. Your current lineup is carrying "
            f"{injured_starters} injured "
            f"starter{'s' if injured_starters != 1 else ''}."
        )
    if priority_board is None or priority_board.empty:
        st.caption(
            "No waiver option materially improves your current roster right now. "
            "Use Waiver Snapshot above for best available by position."
        )
    else:
        render_free_agent_cards(
            priority_board.head(6),
            score_field,
            max_items=6,
            needed_positions=needed_positions,
            key_prefix=f"waivers_priority_{selected_league_id or 'none'}",
        )

    if render_guest_continuity is not None:
        render_guest_continuity()

    if not is_premium:
        if render_premium_lock is not None:
            render_premium_lock(
                "Full waiver board and FAAB shortlist",
                "Priority Adds stay free — Premium adds stashes, watchlist depth, and FAAB shortlist so you do not miss the next claim.",
                feature="Premium Waivers",
            )
        return

    with st.expander("Secondary waiver board", expanded=False):
        st.caption("Upside stashes, watchlist depth, and quick FAAB shortlist. Open this after checking the priority adds.")
        if not stash_candidates.empty:
            st.markdown(
                waiver_section_header_html(
                    "Stash Candidates",
                    kicker="Upside Bench",
                    note="Younger upside bets and players with a clearer path to future usage.",
                    preset="player-list",
                ),
                unsafe_allow_html=True,
            )
            render_free_agent_cards(
                stash_candidates.head(6),
                score_field,
                max_items=6,
                needed_positions=needed_positions,
                key_prefix=f"waivers_stash_{selected_league_id or 'none'}",
            )

        if not watchlist_candidates.empty:
            st.markdown(
                waiver_section_header_html(
                    "Watchlist Depth",
                    kicker="Secondary Board",
                    note="Bench insulation, contingency adds, and position-specific fallback options.",
                    preset="secondary",
                ),
                unsafe_allow_html=True,
            )
            render_free_agent_cards(
                watchlist_candidates.head(6),
                score_field,
                max_items=6,
                needed_positions=needed_positions,
                key_prefix=f"waivers_watch_{selected_league_id or 'none'}",
            )

        if not faab_targets.empty:
            st.markdown(
                waiver_section_header_html(
                    "FAAB Shortlist",
                    kicker="Bid Prep",
                    note="Best quick bid candidates before opening the helper.",
                    preset="primary-action",
                ),
                unsafe_allow_html=True,
            )
            render_free_agent_cards(
                faab_targets.head(4),
                score_field,
                max_items=4,
                needed_positions=needed_positions,
                key_prefix=f"waivers_faab_{selected_league_id or 'none'}",
            )

    with st.expander("Detailed Table View", expanded=False):
        section_id = f"waivers_detailed_table_{selected_league_id or 'none'}"
        if not deferred_rendering.render_section_gate(
            st,
            st.session_state,
            section_id,
            button_label="Load waiver table",
            note="The full waiver table stays collapsed until you need it. Search cards above for the pool.",
        ):
            return
        present = df_free_display
        total_rows = 0 if present is None else int(len(present))
        if total_rows > WAIVERS_DETAILED_TABLE_PREVIEW_ROWS:
            present = present.head(WAIVERS_DETAILED_TABLE_PREVIEW_ROWS)
            st.caption(
                f"Showing top {WAIVERS_DETAILED_TABLE_PREVIEW_ROWS} of {total_rows} available players. "
                "Use search on the cards above for the rest of the pool."
            )
        display_cols = [col for col in waiver_display_cols if col in present.columns]
        display_frame = add_injury_markers(
            format_score_columns(present[display_cols]),
            present,
        ).rename(columns={"player_tier": "Tier"}).reset_index(drop=True)
        from modules import executive_table_ui

        executive_table_ui.render_executive_table_disclosure(
            display_frame,
            title="Waiver board detail",
            primary_column="name" if "name" in display_frame.columns else display_frame.columns[0],
            secondary_columns=tuple(
                column
                for column in ("position", "team", "Tier", score_field)
                if column in display_frame.columns
            ),
            max_summary_rows=10,
            include_expander=False,
            key_suffix="waivers_detail_table",
        )
