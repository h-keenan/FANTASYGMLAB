from html import escape
from typing import Callable

import pandas as pd
import streamlit as st

from modules import league_maturity
from modules import team_eval as team_eval_module
from modules import ui_primitives
from modules import workspace_ui
from modules.roster_needs import TeamNeedsAssessment


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


def build_team_need_presentation(
    metrics: dict | None,
    assessment: TeamNeedsAssessment | None = None,
) -> dict:
    """Separate comparative room weakness from an actionable roster need."""

    relative_weaknesses = tuple(
        dict.fromkeys(
            str(position or "").strip().upper()
            for position in (metrics or {}).get("weaknesses", []) or []
            if str(position or "").strip()
        )
    )
    true_needs = (
        tuple(assessment.true_needs)
        if isinstance(assessment, TeamNeedsAssessment)
        else relative_weaknesses
    )
    covered_relative = tuple(
        position
        for position in relative_weaknesses
        if position not in set(true_needs)
    )

    if true_needs:
        headline_label = "Roster Need"
        headline_value = " / ".join(true_needs[:2])
        headline_note = (
            "Starter/depth coverage identifies a true roster need. "
            + (
                "Also below league average: "
                + " / ".join(
                    position
                    for position in relative_weaknesses
                    if position in set(true_needs)
                )
                + "."
                if any(position in set(true_needs) for position in relative_weaknesses)
                else ""
            )
        ).strip()
    elif relative_weaknesses:
        headline_label = "Relative Weakness"
        headline_value = " / ".join(relative_weaknesses[:2])
        headline_note = (
            "Below league average by comparative room value; current "
            "starter/depth coverage does not classify this as a roster need."
        )
    else:
        headline_label = "Roster Need"
        headline_value = "No true roster need"
        headline_note = "No covered position is being treated as an acquisition need."

    return {
        "true_needs": true_needs,
        "relative_weaknesses": relative_weaknesses,
        "covered_relative_weaknesses": covered_relative,
        "headline_label": headline_label,
        "headline_value": headline_value,
        "headline_note": headline_note,
    }


def _format_score(value) -> str:
    try:
        return f"{int(round(float(value))):,}"
    except Exception:
        return "0"


def _format_rank(value) -> str:
    try:
        rank = int(round(float(value)))
    except Exception:
        return "N/A"
    return f"#{rank}" if rank > 0 else "N/A"


def compact_activity_metric(value) -> str:
    """Keep the Activity column to a short level word so it does not ellipsize."""

    text = " ".join(_safe_text(value).split())
    if not text:
        return "—"
    if text.casefold().endswith(" activity"):
        trimmed = text[: -len(" activity")].strip()
        return trimmed or text
    return text


def _format_age(value) -> str:
    try:
        age = float(value)
    except Exception:
        return ""
    if age <= 0:
        return ""
    return str(int(age)) if age.is_integer() else f"{age:.1f}"


def _rank_fill_width(rank_value, total_count: int, minimum: int = 18) -> int:
    try:
        rank = int(round(float(rank_value)))
    except Exception:
        rank = 0
    total = max(1, int(total_count or 0))
    if rank <= 0:
        return minimum
    points = max(total - rank + 1, 1)
    pct = int(round((points / total) * 100))
    return max(minimum, min(100, pct))


def _truncate_text(value: str, limit: int = 110) -> str:
    text = _safe_text(value).strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "..."


def tidy_label(value):
    if not isinstance(value, str):
        return str(value)
    return value.replace("_", " ").title()


def owner_handle(username: str, fallback: str = "") -> str:
    username = _safe_text(username).strip()
    if username:
        return f"@{username}"
    return _safe_text(fallback).strip()


def league_score_label(score_field: str) -> str:
    if score_field == "dynasty_score":
        return "Dynasty Score"
    if score_field == "rebuild_score":
        return "Rebuild Score"
    return "Value Score"


def _select_intelligence_row(
    df: pd.DataFrame,
    sort_by: list[str],
    ascending,
    mask=None,
):
    if df.empty:
        return None
    subset = df
    if mask is not None:
        try:
            subset = df.loc[mask].copy()
        except Exception:
            subset = df.copy()
        if subset.empty:
            subset = df.copy()
    ordered = subset.sort_values(sort_by, ascending=ascending)
    if ordered.empty:
        return None
    return ordered.iloc[0]


def _intelligence_card(
    label: str,
    row,
    metric: str,
    note: str,
) -> dict:
    if row is None:
        return {
            "label": label,
            "roster_id": "",
            "team_name": "No clear leader",
            "owner_name": "",
            "owner_handle": "",
            "avatar_url": "",
            "metric": metric,
            "note": note,
        }
    return {
        "label": label,
        "roster_id": _safe_text(row.get("roster_id")).strip(),
        "team_name": _safe_text(row.get("team_name"), "Team"),
        "owner_name": _safe_text(row.get("owner_name")),
        "owner_handle": owner_handle(
            row.get("owner_username"),
            row.get("owner_name", ""),
        ),
        "avatar_url": _safe_text(row.get("avatar_url")),
        "metric": metric,
        "note": note,
    }


def build_league_intelligence_cards(
    df_intel: pd.DataFrame,
    score_field: str,
    *,
    has_meaningful_team_injury_impact: Callable,
    team_injury_display_label: Callable,
    maturity_context: dict | None = None,
) -> list[dict]:
    if df_intel.empty:
        return []
    maturity_context = maturity_context or league_maturity.build_league_evidence(
        league_frame=df_intel,
    )

    league_size = len(df_intel)
    contender_mask = (
        df_intel["mode"].astype(str).str.lower().eq("contender")
        if "mode" in df_intel.columns
        else None
    )
    rebuild_mask = (
        df_intel["mode"].astype(str).str.lower().eq("rebuild")
        if "mode" in df_intel.columns
        else None
    )
    top_half_cut = max(1, (league_size + 1) // 2)
    top_heavy_mask = (
        pd.to_numeric(
            df_intel.get("starter_rank", league_size),
            errors="coerce",
        )
        .fillna(league_size)
        .le(top_half_cut)
    )

    youngest = _select_intelligence_row(
        df_intel,
        ["avg_age", "team_name"],
        [True, True],
    )
    oldest = _select_intelligence_row(
        df_intel,
        ["avg_age", "team_name"],
        [False, True],
    )
    strongest_contender = _select_intelligence_row(
        df_intel,
        ["starter_current_score", "power_rank", "team_name"],
        [False, True, True],
        mask=contender_mask,
    )
    best_rebuild = _select_intelligence_row(
        df_intel,
        ["rebuild_index", "draft_capital", "team_name"],
        [False, False, True],
        mask=rebuild_mask,
    )
    most_draft_capital = _select_intelligence_row(
        df_intel,
        ["draft_capital", "first_rounders", "team_name"],
        [False, False, True],
    )
    least_draft_capital = _select_intelligence_row(
        df_intel,
        ["draft_capital", "pick_count", "team_name"],
        [True, True, True],
    )
    most_active_trader = _select_intelligence_row(
        df_intel,
        ["trade_count", "trade_asset_total", "team_name"],
        [False, False, True],
    )
    most_top_heavy = _select_intelligence_row(
        df_intel,
        ["top_heavy_ratio", "starter_share", "team_name"],
        [False, False, True],
        mask=top_heavy_mask,
    )
    deepest_roster = _select_intelligence_row(
        df_intel,
        ["bench_current_score", "team_name"],
        [False, True],
    )
    meaningful_injury_mask = df_intel.apply(
        has_meaningful_team_injury_impact,
        axis=1,
    )
    meaningful_injuries = df_intel[meaningful_injury_mask].copy()
    uncertain_injury_rows = df_intel[
        df_intel.get(
            "injury_data_quality",
            pd.Series("uncertain", index=df_intel.index),
        )
        .fillna("uncertain")
        .astype(str)
        .str.lower()
        .ne("available")
    ].copy()
    most_injured = _select_intelligence_row(
        meaningful_injuries,
        [
            "injury_value_impact",
            "major_injured_starters",
            "injured_starters",
            "team_name",
        ],
        [False, False, False, True],
    )
    most_undervalued = _select_intelligence_row(
        df_intel,
        ["undervalued_gap", "team_name"],
        [False, True],
    )
    youngest_age = _format_age(youngest.get("avg_age")) if youngest is not None else ""
    oldest_age = _format_age(oldest.get("avg_age")) if oldest is not None else ""
    most_injured_summary = (
        _safe_text(
            most_injured.get("actionable_injury_summary")
            or most_injured.get("top_injury_impact_summary")
        )
        if most_injured is not None
        else ""
    )
    no_injury_leader_metric = (
        "Injury data uncertain"
        if not uncertain_injury_rows.empty
        else "No current high-value injury cluster detected"
    )
    no_injury_leader_note = (
        "One or more teams have missing or stale injury updates, so the league cannot be treated as clearly healthy."
        if not uncertain_injury_rows.empty
        else "No team currently clears the value-weighted injury-impact threshold."
    )

    cards = [
        _intelligence_card(
            "Youngest Roster",
            youngest,
            f"Avg age {youngest_age or 'N/A'}",
            "Youth curve advantage across the full roster.",
        ),
        _intelligence_card(
            "Oldest Roster",
            oldest,
            f"Avg age {oldest_age or 'N/A'}",
            "Veteran-heavy build that may need a timing check soon.",
        ),
        _intelligence_card(
            "Strongest Contender",
            strongest_contender,
            f"Starter score {_format_score(strongest_contender.get('starter_current_score')) if strongest_contender is not None else '0'}",
            "Best weekly lineup punch among teams currently tagged as contenders.",
        ),
        _intelligence_card(
            "Best Rebuild",
            best_rebuild,
            (
                f"{_format_score(best_rebuild.get('draft_capital'))} draft capital"
                if best_rebuild is not None
                else "0 draft capital"
            ),
            "Strong blend of youth, picks, and enough base value to build forward.",
        ),
        _intelligence_card(
            "Most Draft Capital",
            most_draft_capital,
            (
                f"{_format_score(most_draft_capital.get('draft_capital'))} | {int(most_draft_capital.get('first_rounders') or 0)} firsts"
                if most_draft_capital is not None
                else "0"
            ),
            "Most future flexibility in the league right now.",
        ),
        _intelligence_card(
            "Least Draft Capital",
            least_draft_capital,
            (
                f"{_format_score(least_draft_capital.get('draft_capital'))} | {int(least_draft_capital.get('pick_count') or 0)} picks"
                if least_draft_capital is not None
                else "0"
            ),
            "Thin future cupboard compared with the rest of the league.",
        ),
        _intelligence_card(
            "Most Active Trader",
            (
                most_active_trader
                if league_maturity.insight_is_available(
                    "most_active_trader", maturity_context
                )
                and most_active_trader is not None
                and int(most_active_trader.get("trade_count") or 0) > 0
                else None
            ),
            (
                f"{int(most_active_trader.get('trade_count') or 0)} completed trades"
                if league_maturity.insight_is_available(
                    "most_active_trader", maturity_context
                )
                and most_active_trader is not None
                and int(most_active_trader.get("trade_count") or 0) > 0
                else "Waiting for completed trade history"
            ),
            (
                "Based on completed Sleeper trade transactions across the season."
                if league_maturity.insight_is_available(
                    "most_active_trader", maturity_context
                )
                else league_maturity.evidence_status(
                    "most_active_trader", maturity_context
                )["message"]
            ),
        ),
        _intelligence_card(
            "Most Top-Heavy Roster",
            most_top_heavy,
            (
                f"{int(round((float(most_top_heavy.get('starter_share') or 0)) * 100))}% starter share"
                if most_top_heavy is not None
                else "0%"
            ),
            "Big lineup punch up top, with less of the score living on the bench.",
        ),
        _intelligence_card(
            "Deepest Roster",
            deepest_roster,
            f"Bench score {_format_score(deepest_roster.get('bench_current_score')) if deepest_roster is not None else '0'}",
            "Best non-starter depth using the current valuation lens.",
        ),
        _intelligence_card(
            "Most Injured Roster",
            most_injured,
            (
                f"{team_injury_display_label(most_injured)} | "
                f"Impact {_format_score(most_injured.get('injury_value_impact'))}"
                if most_injured is not None
                else no_injury_leader_metric
            ),
            (
                _truncate_text(
                    " | ".join(
                        part
                        for part in [
                            most_injured_summary,
                            (
                                _safe_text(most_injured.get("injury_data_note"))
                                if _safe_text(
                                    most_injured.get("injury_data_quality"),
                                    "available",
                                )
                                != "available"
                                else ""
                            ),
                        ]
                        if part
                    ),
                    220,
                )
                if most_injured is not None
                else no_injury_leader_note
            ),
        ),
        _intelligence_card(
            "Most Undervalued Roster",
            most_undervalued,
            (
                f"+{_format_score(most_undervalued.get('undervalued_gap'))} vs market"
                if most_undervalued is not None
                and float(most_undervalued.get("undervalued_gap") or 0) >= 0
                else f"{_format_score(most_undervalued.get('undervalued_gap')) if most_undervalued is not None else '0'} vs market"
            ),
            f"Biggest positive gap between total {league_score_label(score_field).lower()} and market score.",
        ),
    ]
    return cards


def _league_overview_team_lines(
    df: pd.DataFrame,
    *,
    limit: int = 3,
    include_power: bool = False,
    include_franchise: bool = False,
    include_draft: bool = False,
    include_strategy: bool = False,
    include_health: bool = False,
    team_injury_display_label: Callable | None = None,
) -> list[str]:
    if df is None or df.empty:
        return []

    items: list[str] = []
    for _, row in df.head(limit).iterrows():
        team_name = _safe_text(row.get("team_name"), "Team")
        details: list[str] = []
        if include_power:
            details.append(f"Power {_format_rank(row.get('power_rank'))}")
        if include_franchise:
            details.append(f"Franchise {_format_rank(row.get('franchise_rank'))}")
        if include_draft:
            details.append(f"Draft {_format_rank(row.get('draft_capital_rank'))}")
        if include_strategy:
            details.append(
                _safe_text(
                    row.get("strategy_display"),
                    tidy_label(row.get("mode", "unknown")),
                )
            )
        if include_health and team_injury_display_label is not None:
            health_flag = team_injury_display_label(row)
            if health_flag:
                injured_starters = _safe_positive_int(
                    row.get("injured_starters"),
                    0,
                )
                details.append(f"{health_flag} ({injured_starters} starters)")
        items.append(
            team_name + (f" | {' | '.join(details)}" if details else "")
        )
    return items


def build_league_overview_decision_cards(
    df_intel: pd.DataFrame,
    *,
    team_injury_display_label: Callable,
    maturity_context: dict | None = None,
) -> list[dict]:
    if df_intel is None or df_intel.empty:
        return []
    maturity_context = maturity_context or league_maturity.build_league_evidence(
        league_frame=df_intel,
    )

    league_size = len(df_intel)
    working = df_intel.copy()
    numeric_defaults = {
        "power_rank": league_size,
        "franchise_rank": league_size,
        "draft_capital_rank": league_size,
        "draft_capital": 0.0,
        "first_rounders": 0.0,
        "pick_count": 0.0,
        "injury_burden": 0.0,
        "injured_starters": 0.0,
        "trade_count": 0.0,
    }
    for column, default in numeric_defaults.items():
        working[column] = pd.to_numeric(
            working.get(column),
            errors="coerce",
        ).fillna(default)

    working["strategy_key"] = working.apply(
        lambda row: team_eval_module.normalize_team_strategy(
            row.get("strategy") or row.get("mode")
        ),
        axis=1,
    )
    working["pressure_score"] = (
        working["power_rank"] * 1.0
        + working["franchise_rank"] * 0.9
        + working["draft_capital_rank"] * 0.7
        + working["injury_burden"] * 0.35
        + working["injured_starters"] * 0.6
    )
    working = working.sort_values(
        ["power_rank", "franchise_rank", "team_name"],
        ascending=[True, True, True],
    ).reset_index(drop=True)

    top_cut = max(2, league_size // 3)
    middle_low = min(league_size, top_cut + 1)
    middle_high = max(middle_low, league_size - top_cut)
    midpoint = (league_size + 1) / 2.0
    working["middle_distance"] = (
        (working["power_rank"] - midpoint).abs()
        + (working["franchise_rank"] - midpoint).abs()
        + ((working["draft_capital_rank"] - midpoint).abs() * 0.45)
    )

    pressure_teams = working.sort_values(
        ["pressure_score", "power_rank", "franchise_rank", "team_name"],
        ascending=[False, False, False, True],
    ).head(3)

    stuck_middle = working[
        working["power_rank"].between(middle_low, middle_high)
        & working["franchise_rank"].between(middle_low, middle_high)
        & ~working["strategy_key"].isin({"contender", "rebuild", "tank"})
    ].copy()
    if stuck_middle.empty:
        stuck_middle = working[
            ~working["strategy_key"].isin({"contender", "rebuild", "tank"})
        ].sort_values(
            ["middle_distance", "team_name"],
            ascending=[True, True],
        ).head(3)

    buyer_teams = working[
        working["strategy_key"].isin({"contender", "fringe_contender"})
    ].sort_values(
        ["power_rank", "draft_capital_rank", "team_name"],
        ascending=[True, True, True],
    ).head(2)
    seller_teams = working[
        working["strategy_key"].isin({"rebuild", "tank", "retool"})
    ].sort_values(
        ["draft_capital_rank", "franchise_rank", "team_name"],
        ascending=[True, True, True],
    ).head(2)
    if seller_teams.empty:
        seller_teams = pressure_teams.head(2)

    buyer_names = (
        ", ".join(
            _safe_text(row.get("team_name"))
            for _, row in buyer_teams.iterrows()
        )
        or "No clear buyer cluster yet."
    )
    seller_names = (
        ", ".join(
            _safe_text(row.get("team_name"))
            for _, row in seller_teams.iterrows()
        )
        or "No clear seller cluster yet."
    )
    pivot_names = (
        ", ".join(
            _safe_text(row.get("team_name"))
            for _, row in stuck_middle.head(2).iterrows()
        )
        or "No clear pivot teams yet."
    )

    return [
        {
            "label": "Pressure Teams",
            "title": "Bottom-tier rosters with the most immediate strain",
            "tone": "weakness",
            "items": _league_overview_team_lines(
                pressure_teams,
                include_power=True,
                include_franchise=True,
                include_draft=True,
                include_health=True,
                team_injury_display_label=team_injury_display_label,
            ),
        },
        {
            "label": "Stuck Middle",
            "title": "Teams that may need a clearer direction",
            "tone": "risk",
            "items": _league_overview_team_lines(
                stuck_middle,
                include_power=True,
                include_franchise=True,
                include_strategy=True,
                team_injury_display_label=team_injury_display_label,
            ),
        },
        {
            "label": "Partner Types",
            "title": (
                "Who is most likely to buy, sell, or pivot"
                if league_maturity.insight_is_available(
                    "likely_buyers", maturity_context
                )
                and league_maturity.insight_is_available(
                    "likely_sellers", maturity_context
                )
                else "Partner tendencies are still forming"
            ),
            "tone": "opportunity",
            "items": (
                [
                    f"Likely buyers: {buyer_names}",
                    f"Likely sellers: {seller_names}",
                    f"Pivot teams: {pivot_names}",
                ]
                if league_maturity.insight_is_available(
                    "likely_buyers", maturity_context
                )
                and league_maturity.insight_is_available(
                    "likely_sellers", maturity_context
                )
                else [
                    league_maturity.evidence_status(
                        "likely_buyers", maturity_context
                    )["message"],
                    "Use current roster needs and surplus rooms until transaction history develops.",
                ]
            ),
        },
    ]


def ranked_leaderboard_row_html(
    *,
    rank_label: str,
    team_name: str,
    owner_text: str,
    primary_metric: str,
    metric_label: str,
    interpretation: str = "",
    secondary: str = "",
    logo_html: str,
    tap_class: str = "",
    tap_attrs: str = "",
    top_three: bool = False,
    is_current: bool = False,
    status_category: str = "",
    status_subtype: str = "",
    exception: str = "",
    density: str = "compact",
) -> str:
    """Dense ranked row: lead → identity → metric → status → meta → exception."""

    from modules import dense_list_primitives

    classes = ["dg-ranked-row", "dg-dense-row", "dg-ui-card"]
    density_key = density if density in {"compact", "standard", "rich"} else "compact"
    classes.append(f"dg-dense-row--{density_key}")
    if top_three:
        classes.append("dg-ranked-row--top")
    if is_current:
        classes.append("dg-ranked-row--current")
    if tap_class:
        classes.append(tap_class.strip())

    category = status_category or interpretation
    subtype = status_subtype
    status_html = dense_list_primitives.dense_status_html(category, subtype)
    if not status_html and interpretation:
        status_html = (
            f"<div class='dg-dense-status dg-ranked-interp'>"
            f"<span class='dg-dense-status__primary'>{escape(interpretation)}</span>"
            f"</div>"
        )
    meta_html = ""
    if secondary:
        meta_html = dense_list_primitives.dense_meta_html(
            *[part.strip() for part in secondary.split("·") if part.strip()]
        )
        meta_html = meta_html.replace("dg-dense-meta'", "dg-dense-meta dg-ranked-secondary'")
    if status_html and "dg-ranked-interp" not in status_html:
        status_html = status_html.replace(
            "dg-dense-status'",
            "dg-dense-status dg-ranked-interp'",
        )
    exception_html = (
        dense_list_primitives.dense_exception_html(
            exception,
            label="Starter availability",
        )
        if exception
        else ""
    )
    metric_html = dense_list_primitives.dense_metric_html(primary_metric, metric_label)
    # Keep legacy metric class hooks for existing selectors/tests.
    metric_html = metric_html.replace("dg-dense-metric'", "dg-dense-metric dg-ranked-metric'")
    metric_html = metric_html.replace(
        "dg-dense-metric__value'",
        "dg-dense-metric__value dg-ranked-metric-value'",
    )
    metric_html = metric_html.replace(
        "dg-dense-metric__label'",
        "dg-dense-metric__label dg-ranked-metric-label'",
    )
    trail_html = (
        f"<div class='dg-dense-trail'>{status_html}{meta_html}{exception_html}</div>"
        if (status_html or meta_html or exception_html)
        else ""
    )

    return (
        f"<div class='{' '.join(classes)}'{tap_attrs}>"
        f"<div class='dg-dense-lead dg-ranked-rank' aria-label='Rank {escape(rank_label)}'>"
        f"{escape(rank_label)}</div>"
        f"<div class='dg-dense-identity dg-ranked-identity'>"
        f"{logo_html}"
        f"<div class='dg-dense-identity__copy dg-ranked-copy'>"
        f"<div class='dg-dense-identity__primary dg-ranked-team'>{escape(team_name)}</div>"
        f"<div class='dg-dense-identity__secondary dg-ranked-owner'>{escape(owner_text)}</div>"
        f"</div></div>"
        f"{metric_html}"
        f"{trail_html}"
        f"</div>"
    )


def filter_league_insight_leader_cards(
    cards: list[dict],
    *,
    omit_labels: tuple[str, ...] = (),
) -> list[dict]:
    """Presentation filter for leader cards already covered by primary boards."""

    if not cards:
        return []
    omitted = {label for label in omit_labels if label}
    if not omitted:
        return list(cards)
    return [
        card
        for card in cards
        if _safe_text(card.get("label")) not in omitted
    ]


def render_league_intelligence_cards(
    cards: list[dict],
    *,
    team_tap_markup: Callable,
    render_team_card_tap_grid: Callable,
    open_league_team_from_tap: Callable,
    team_logo_html: Callable,
    current_roster_id: object = None,
):
    if not cards:
        return
    current_key = _safe_text(current_roster_id).strip()
    card_html = []
    for idx, card in enumerate(cards):
        tap_class, tap_attrs = team_tap_markup(card)
        roster_key = _safe_text(card.get("roster_id")).strip()
        current_class = (
            " dg-ranked-row--current"
            if current_key and roster_key and roster_key == current_key
            else ""
        )
        supporting_class = " dg-intel-card--supporting" if idx > 0 else ""
        card_html.append(
            "<article class='dg-intel-card dg-ui-card dg-ui-card--elevated"
            + tap_class
            + current_class
            + supporting_class
            + "' id='dg-intel-card-"
            + str(idx)
            + "'"
            + tap_attrs
            + ">"
            + f"<div class='dg-intel-kicker'>{escape(_safe_text(card.get('label')))}</div>"
            + "<div class='dg-intel-team-row'>"
            + team_logo_html(
                _safe_text(card.get("avatar_url")),
                _safe_text(card.get("team_name")),
                css_class="dg-intel-logo-wrap",
            )
            + "<div class='dg-intel-team-copy'>"
            + f"<div class='dg-intel-title'>{escape(_safe_text(card.get('team_name'), 'No clear leader'))}</div>"
            + f"<div class='dg-intel-owner'>{escape(_safe_text(card.get('owner_handle') or card.get('owner_name')))}</div>"
            + "</div></div>"
            + f"<div class='dg-intel-metric'>{escape(_safe_text(card.get('metric')))}</div>"
            + f"<div class='dg-intel-note'>{escape(_safe_text(card.get('note')))}</div>"
            + "</article>"
        )
    clicked = render_team_card_tap_grid(
        html="<div class='dg-intel-grid'>" + "".join(card_html) + "</div>",
        key_prefix="league_intelligence_cards",
    )
    if open_league_team_from_tap(clicked):
        st.rerun()


def _board_secondary_parts(
    row,
    *,
    rank_column: str,
    starter_rank: str,
    bench_rank: str,
    draft_rank: str,
    franchise_rank: str,
    power_rank: str,
) -> list[str]:
    """Omit the board's own primary rank from the secondary line."""

    if rank_column == "power_rank":
        return [
            f"Franchise {franchise_rank}",
            f"Draft {draft_rank}",
            f"Starter {starter_rank}",
        ]
    if rank_column == "franchise_rank":
        return [
            f"Power {power_rank}",
            f"Draft {draft_rank}",
            f"Starter {starter_rank}",
        ]
    if rank_column == "draft_capital_rank":
        firsts = _safe_positive_int(row.get("first_rounders"), 0)
        return [
            f"Power {power_rank}",
            f"Franchise {franchise_rank}",
            f"{firsts} firsts" if firsts else f"Picks {_safe_positive_int(row.get('pick_count'), 0)}",
        ]
    return [
        f"Power {power_rank}",
        f"Franchise {franchise_rank}",
        f"Starter {starter_rank}",
        f"Bench {bench_rank}",
        f"Draft {draft_rank}",
    ]


def render_power_rankings_board(
    df_display: pd.DataFrame,
    score_label: str,
    rank_column: str = "power_rank",
    score_column: str = "power_score",
    *,
    has_meaningful_team_injury_impact: Callable,
    team_injury_display_label: Callable,
    team_tap_markup: Callable,
    render_team_card_tap_grid: Callable,
    open_league_team_from_tap: Callable,
    team_logo_html: Callable,
    current_roster_id: object = None,
):
    if df_display.empty:
        return
    board_rows = []
    ordered = df_display.sort_values(
        [rank_column, score_column],
        ascending=[True, False],
    ).reset_index(drop=True)
    current_key = _safe_text(current_roster_id).strip()
    metric_label = _safe_text(score_label, "Score")
    for _, row in ordered.iterrows():
        owner_text = owner_handle(
            row.get("owner_username"),
            row.get("owner_name", "Owner"),
        )
        strategy_text = _safe_text(
            row.get("strategy_display"),
            tidy_label(row.get("mode", "unknown")),
        )
        archetype_text = _safe_text(row.get("archetype_label"))
        rank_value = int(
            pd.to_numeric(
                pd.Series([row.get(rank_column)]),
                errors="coerce",
            )
            .fillna(0)
            .iloc[0]
        )
        starter_rank = _format_rank(row.get("starter_rank"))
        bench_rank = _format_rank(row.get("bench_rank"))
        draft_rank = _format_rank(row.get("draft_capital_rank"))
        franchise_rank = _format_rank(row.get("franchise_rank"))
        power_rank = _format_rank(row.get("power_rank"))
        injured_starters = _safe_positive_int(
            row.get("injured_starters"),
            0,
        )
        health_bits = []
        if has_meaningful_team_injury_impact(row):
            health_bits.append(team_injury_display_label(row))
            if injured_starters > 0:
                health_bits.append(f"{injured_starters} starters")
        secondary_parts = _board_secondary_parts(
            row,
            rank_column=rank_column,
            starter_rank=starter_rank,
            bench_rank=bench_rank,
            draft_rank=draft_rank,
            franchise_rank=franchise_rank,
            power_rank=power_rank,
        )
        roster_key = _safe_text(row.get("roster_id")).strip()
        tap_class, tap_attrs = team_tap_markup(row)
        board_rows.append(
            ranked_leaderboard_row_html(
                rank_label=_format_rank(rank_value),
                team_name=_safe_text(row.get("team_name")),
                owner_text=owner_text,
                primary_metric=_format_score(row.get(score_column)),
                metric_label=metric_label,
                status_category=strategy_text,
                status_subtype=archetype_text,
                secondary=" · ".join(secondary_parts),
                exception=" · ".join(bit for bit in health_bits if bit),
                logo_html=team_logo_html(
                    _safe_text(row.get("avatar_url")),
                    _safe_text(row.get("team_name")),
                    css_class="dg-ranked-logo",
                ),
                tap_class=tap_class,
                tap_attrs=tap_attrs,
                top_three=bool(rank_value and rank_value <= 3),
                is_current=bool(current_key and roster_key and roster_key == current_key),
                density="compact",
            )
        )
    clicked = render_team_card_tap_grid(
        html=(
            "<div class='dg-ranked-board' "
            f"aria-label='{escape(metric_label)} leaderboard'>"
            + "".join(board_rows)
            + "</div>"
        ),
        key_prefix=f"league_{rank_column}_{score_column}",
    )
    if open_league_team_from_tap(clicked):
        st.rerun()


def team_comparison_row_html(
    *,
    power_rank: str,
    franchise_rank: str,
    team_name: str,
    owner_text: str,
    archetype: str,
    style_philosophy: str,
    activity: str,
    logo_html: str,
    tap_class: str = "",
    tap_attrs: str = "",
    is_current: bool = False,
) -> str:
    """Compact league comparison row: ranks, identity, archetype, style, activity."""

    from modules import dense_list_primitives

    classes = ["dg-ranked-row", "dg-dense-row", "dg-dense-row--compact", "dg-ui-card"]
    if is_current:
        classes.append("dg-ranked-row--current")
    if tap_class:
        classes.append(tap_class.strip())
    lead_html = dense_list_primitives.dense_dual_rank_html(
        power=power_rank,
        franchise=franchise_rank,
    )
    identity_html = (
        "<div class='dg-dense-identity dg-ranked-identity'>"
        f"{logo_html}"
        "<div class='dg-dense-identity__copy dg-ranked-copy'>"
        f"<div class='dg-dense-identity__primary dg-ranked-team'>{escape(team_name)}</div>"
        f"<div class='dg-dense-identity__secondary dg-ranked-owner'>{escape(owner_text)}</div>"
        "</div></div>"
    )
    metric_html = dense_list_primitives.dense_metric_html(
        compact_activity_metric(activity),
        "Activity",
        compact_label=False,
    )
    trail_html = dense_list_primitives.dense_trail_html(
        status_html=dense_list_primitives.dense_status_html(archetype, ""),
        meta_html=dense_list_primitives.dense_meta_html(
            *[part.strip() for part in str(style_philosophy or "").split("·") if part.strip()]
        ),
    )
    return (
        f"<div class='{' '.join(classes)}'{tap_attrs}>"
        f"{lead_html}{identity_html}{metric_html}{trail_html}</div>"
    )


def render_team_comparison_board(
    df_display: pd.DataFrame,
    *,
    team_tap_markup: Callable,
    render_team_card_tap_grid: Callable,
    open_league_team_from_tap: Callable,
    team_logo_html: Callable,
    current_roster_id: object = None,
) -> None:
    """Primary League Overview comparison — dense rows, no spreadsheet scroll."""

    if df_display is None or df_display.empty:
        return
    sort_cols = [col for col in ("power_rank", "franchise_rank") if col in df_display.columns]
    ordered = df_display.sort_values(sort_cols, ascending=True) if sort_cols else df_display
    ordered = ordered.reset_index(drop=True)
    current_key = _safe_text(current_roster_id).strip()
    board_rows = []
    for _, row in ordered.iterrows():
        owner_text = owner_handle(
            row.get("owner_username"),
            row.get("owner_name", "Owner"),
        )
        style_bits = [
            _safe_text(row.get("trading_style")),
            _safe_text(row.get("roster_philosophy")),
            _safe_text(row.get("asset_behavior")),
        ]
        roster_key = _safe_text(row.get("roster_id")).strip()
        tap_class, tap_attrs = team_tap_markup(row)
        board_rows.append(
            team_comparison_row_html(
                power_rank=_format_rank(row.get("power_rank")),
                franchise_rank=_format_rank(row.get("franchise_rank")),
                team_name=_safe_text(row.get("team_name")),
                owner_text=owner_text,
                archetype=_safe_text(row.get("archetype_label")),
                style_philosophy=" · ".join(bit for bit in style_bits if bit),
                activity=_safe_text(row.get("activity_level")),
                logo_html=team_logo_html(
                    _safe_text(row.get("avatar_url")),
                    _safe_text(row.get("team_name")),
                    css_class="dg-ranked-logo",
                ),
                tap_class=tap_class,
                tap_attrs=tap_attrs,
                is_current=bool(current_key and roster_key and roster_key == current_key),
            )
        )
    clicked = render_team_card_tap_grid(
        html=(
            "<div class='dg-ranked-board dg-team-comparison-board' "
            "aria-label='Team comparison by power and franchise'>"
            + "".join(board_rows)
            + "</div>"
        ),
        key_prefix="league_team_comparison",
    )
    if open_league_team_from_tap(clicked):
        st.rerun()


def render_standings_board(
    standings_bundle: dict,
    *,
    team_tap_markup: Callable,
    render_team_card_tap_grid: Callable,
    open_league_team_from_tap: Callable,
    team_logo_html: Callable,
    current_roster_id: object = None,
):
    """Render Sleeper standings with executive ranked rows (results, not power)."""

    if not isinstance(standings_bundle, dict):
        ui_primitives.render_empty_state_panel(
            "Standings unavailable",
            "League results normally appear here once Sleeper matchup records are readable.",
            kind="no-data",
            recovery_guidance="Refresh after the league has posted regular-season results.",
        )
        return
    if not standings_bundle.get("available"):
        ui_primitives.render_empty_state_panel(
            "Standings not ready yet",
            _safe_text(
                standings_bundle.get("message"),
                "Wins, losses, and points for appear here after regular-season games start.",
            ),
            kind="no-data",
            recovery_guidance="Nothing to do now — this board unlocks with league results.",
        )
        return

    current_key = _safe_text(current_roster_id).strip()
    groups = standings_bundle.get("groups") or []
    for group in groups:
        frame = group.get("frame")
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        rank_column = _safe_text(group.get("rank_column"), "standing_rank") or "standing_rank"
        group_label = _safe_text(group.get("label"))
        if group_label:
            st.markdown(
                f"<div class='dg-standings-division-label'>{escape(group_label)}</div>",
                unsafe_allow_html=True,
            )
        board_chunks: list[str] = []
        for _, row in frame.iterrows():
            rank_value = _safe_positive_int(row.get(rank_column), 0)
            if rank_value <= 0:
                continue
            owner_text = owner_handle(
                row.get("owner_username"),
                row.get("owner_name", "Manager"),
            )
            record_label = _safe_text(row.get("record_label"), "0-0")
            win_pct_label = _safe_text(row.get("win_pct_label"), "—")
            points_for_label = _safe_text(row.get("points_for_label"), "0.0")
            points_against_label = _safe_text(row.get("points_against_label"), "0.0")
            playoff_status = _safe_text(row.get("playoff_status"))
            division_label = _safe_text(row.get("division_label"))
            interpretation_parts = [f"Win% {win_pct_label}", f"PF {points_for_label}"]
            if playoff_status:
                interpretation_parts.append(playoff_status)
            secondary_parts = [f"PA {points_against_label}"]
            if division_label and not group_label:
                secondary_parts.insert(0, division_label)
            standing_rank = _safe_positive_int(row.get("standing_rank"), rank_value)
            roster_key = _safe_text(row.get("roster_id")).strip()
            tap_class, tap_attrs = team_tap_markup(row)
            aria_bits = [
                f"Standings rank {rank_value}",
                _safe_text(row.get("team_name"), "Team"),
                record_label,
            ]
            if playoff_status:
                aria_bits.append(playoff_status)
            if tap_attrs and "aria-label=" not in tap_attrs:
                tap_attrs = (
                    tap_attrs
                    + f" aria-label='{escape(' · '.join(aria_bits), quote=True)}'"
                )
            board_chunks.append(
                ranked_leaderboard_row_html(
                    rank_label=_format_rank(rank_value),
                    team_name=_safe_text(row.get("team_name"), "Team"),
                    owner_text=owner_text or "Manager",
                    primary_metric=record_label,
                    metric_label="Record",
                    interpretation=" · ".join(interpretation_parts),
                    secondary=" · ".join(secondary_parts),
                    logo_html=team_logo_html(
                        _safe_text(row.get("avatar_url")),
                        _safe_text(row.get("team_name"), "Team"),
                        css_class="dg-ranked-logo",
                    ),
                    tap_class=tap_class,
                    tap_attrs=tap_attrs,
                    top_three=bool(standing_rank and standing_rank <= 3),
                    is_current=bool(
                        current_key and roster_key and roster_key == current_key
                    ),
                )
            )
            if bool(row.get("on_playoff_line")):
                board_chunks.append(
                    "<div class='dg-standings-playoff-line' role='separator' "
                    "aria-label='Playoff line'>Playoff line</div>"
                )
        if not board_chunks:
            continue
        clicked = render_team_card_tap_grid(
            html=(
                "<div class='dg-ranked-board dg-ranked-board--standings' "
                "aria-label='League standings'>"
                + "".join(board_chunks)
                + "</div>"
            ),
            key_prefix=f"league_standings_{_safe_text(group.get('key'), 'league')}",
        )
        if open_league_team_from_tap(clicked):
            st.rerun()


def render_team_rank_cards(team_row: dict):
    """Team comparative ranks via canonical summary tiles."""

    card_specs = [
        (
            "Power Rank",
            team_row.get("power_rank"),
            "Strongest lineup and depth right now",
            "power",
        ),
        (
            "Franchise Rank",
            team_row.get("franchise_rank"),
            "Full roster value plus future assets",
            "franchise",
        ),
        (
            "Roster Value Rank",
            team_row.get("roster_value_rank"),
            "All-player roster value",
            "metric",
        ),
        ("Starter Rank", team_row.get("starter_rank"), "Best weekly lineup", "metric"),
        ("Bench Rank", team_row.get("bench_rank"), "Depth behind starters", "metric"),
        ("Age Rank", team_row.get("age_rank"), "Younger roster ranks higher", "metric"),
        (
            "Draft Capital Rank",
            team_row.get("draft_capital_rank"),
            "Owned future picks",
            "metric",
        ),
    ]
    items = []
    for label, value, note, tone in card_specs:
        rank_text = f"#{int(value)}" if value and pd.notna(value) else "N/A"
        items.append(
            {
                "label": label,
                "value": rank_text,
                "note": note,
                "tone": tone,
                "tappable": False,
            }
        )
    workspace_ui.render_summary_tiles(
        items,
        compact=True,
        key_prefix="team_rank_cards",
    )


def render_team_score_details(team_row: dict, score_label: str):
    score_specs = [
        ("Power Score", team_row.get("power_score")),
        ("Franchise Score", team_row.get("franchise_score")),
        ("Starter-Weighted Base", team_row.get("total_score")),
        ("Starter Score", team_row.get("starter_score")),
        ("Bench Score", team_row.get("bench_score")),
        ("Raw Roster Score", team_row.get("raw_roster_score")),
        ("Draft Capital", team_row.get("draft_capital")),
        ("QB Score", team_row.get("qb_score")),
        ("RB Score", team_row.get("rb_score")),
        ("WR Score", team_row.get("wr_score")),
        ("TE Score", team_row.get("te_score")),
    ]
    cells = []
    for label, value in score_specs:
        cells.append(
            "<div class='team-score-item dg-ui-card'>"
            + f"<div class='team-score-name'>{escape(label)}</div>"
            + f"<div class='team-score-value'>{escape(_format_score(value))}</div>"
            + "</div>"
        )
    st.markdown(
        "<div class='team-section-card'>"
        f"<div class='team-section-title'>Detailed Scores · {escape(_safe_text(score_label, 'Scores'))}</div>"
        "<div class='team-score-grid'>"
        + "".join(cells)
        + "</div></div>",
        unsafe_allow_html=True,
    )


def build_team_partner_context_tiles(
    team_row: dict | None,
    metrics: dict | None,
    draft_row: dict | None,
    league_size: int,
    maturity_context: dict | None = None,
    team_needs_assessment: TeamNeedsAssessment | None = None,
) -> list[dict]:
    team_row = team_row or {}
    metrics = metrics or {}
    draft_row = draft_row or {}
    strategy_key = team_eval_module.normalize_team_strategy(
        team_row.get("strategy") or team_row.get("mode")
    )
    strategy_label = _safe_text(
        team_row.get("strategy_display"),
        team_eval_module.team_strategy_label(strategy_key),
    )
    trade_style = _safe_text(team_row.get("trading_style"), "Unknown")
    implication = _safe_text(team_row.get("manager_trade_implication"))
    draft_rank = _safe_positive_int(
        draft_row.get("draft_capital_rank"),
        0,
    )
    draft_capital = _format_score(draft_row.get("draft_capital"))

    history_available = (
        league_maturity.insight_is_available(
            "likely_buyers", maturity_context
        )
        and league_maturity.insight_is_available(
            "likely_sellers", maturity_context
        )
    )
    if strategy_key in {"contender", "fringe_contender"}:
        partner_type = "Likely Buyer" if history_available else "Contender Profile"
        partner_note = (
            implication
            if history_available and implication
            else "Current roster direction points toward immediate starter value; no transaction tendency is inferred yet."
        )
        tone = "power"
    elif strategy_key in {"rebuild", "tank"}:
        partner_type = "Likely Seller" if history_available else "Rebuild Profile"
        partner_note = (
            implication
            if history_available and implication
            else "Current roster direction favors youth and future flexibility; no transaction tendency is inferred yet."
        )
        tone = "opportunity"
    else:
        partner_type = "Pivot Team" if history_available else "Balanced Profile"
        partner_note = (
            implication
            if history_available and implication
            else "Current roster construction does not create a strong historical buyer or seller conclusion."
        )
        tone = "strategy"

    if draft_rank and league_size > 1:
        if draft_rank <= max(2, league_size // 3):
            draft_posture = "Pick-Rich"
            draft_note = (
                f"Draft rank {_format_rank(draft_rank)} | {draft_capital} "
                "capital gives this team room to spend or stay patient."
            )
        elif draft_rank >= max(
            league_size - max(2, league_size // 3) + 1,
            1,
        ):
            draft_posture = "Pick-Poor"
            draft_note = (
                f"Draft rank {_format_rank(draft_rank)} | {draft_capital} "
                "capital means future flexibility is relatively thin."
            )
        else:
            draft_posture = "Balanced Picks"
            draft_note = (
                f"Draft rank {_format_rank(draft_rank)} | {draft_capital} "
                "capital keeps this team flexible but not overloaded with picks."
            )
    else:
        draft_posture = "Draft TBD"
        draft_note = "No strong draft-capital edge is standing out yet."

    strengths = [
        str(pos).upper() for pos in metrics.get("strengths", []) or []
    ]
    need_presentation = build_team_need_presentation(
        metrics,
        team_needs_assessment,
    )
    true_needs = list(need_presentation["true_needs"])
    covered_relative = list(
        need_presentation["covered_relative_weaknesses"]
    )
    room_note_parts = []
    if strengths:
        room_note_parts.append("Surplus: " + " / ".join(strengths[:2]))
    if true_needs:
        room_note_parts.append("Roster need: " + " / ".join(true_needs[:2]))
    if covered_relative:
        room_note_parts.append(
            "Below league average: " + " / ".join(covered_relative[:2])
        )
    room_note = (
        " | ".join(room_note_parts)
        or "No clear surplus or pressure point is separating this roster yet."
    )

    return [
        {
            "label": "Partner Type",
            "value": partner_type,
            "note": partner_note,
            "tone": tone,
        },
        {
            "label": "Draft Posture",
            "value": draft_posture,
            "note": draft_note,
            "tone": "franchise",
        },
        {
            "label": "Negotiation Lens",
            "value": strategy_label or "Balanced",
            "note": f"{trade_style} manager | {room_note}",
            "tone": "trade",
        },
    ]


def render_archetype_summary(
    team_row: pd.Series | dict | None,
    *,
    compact: bool = False,
    show_header: bool = True,
):
    if isinstance(team_row, dict):
        team = team_row
    elif team_row is not None and hasattr(team_row, "to_dict"):
        team = team_row.to_dict()
    else:
        team = {}

    archetype_label = _safe_text(team.get("archetype_label"))
    if not archetype_label:
        return

    if show_header:
        workspace_ui.render_section_header(
            "League Archetype",
            kicker="Franchise Identity",
            note="A more specific franchise subtype built on top of the current strategy label.",
            compact=compact,
        )
    workspace_ui.render_summary_tiles(
        [
            {
                "label": "Archetype",
                "value": archetype_label,
                "note": _safe_text(
                    team.get("archetype_explanation"),
                    "No archetype explanation available yet.",
                ),
                "tone": "franchise",
            }
        ]
    )
    workspace_ui.render_analysis_cards(
        [
            {
                "label": "Strengths",
                "title": "What this archetype does well",
                "items": list(team.get("archetype_strengths") or []),
                "tone": "strength",
            },
            {
                "label": "Risks",
                "title": "What can go wrong",
                "items": list(team.get("archetype_risks") or []),
                "tone": "risk",
            },
            {
                "label": "Recommendations",
                "title": "How to play it",
                "items": list(team.get("archetype_recommendations") or []),
                "tone": "opportunity",
            },
        ]
    )


def render_manager_tendencies_summary(
    team_row: pd.Series | dict | None,
    *,
    compact: bool = False,
    show_header: bool = True,
    maturity_context: dict | None = None,
):
    if isinstance(team_row, dict):
        team = team_row
    elif team_row is not None and hasattr(team_row, "to_dict"):
        team = team_row.to_dict()
    else:
        team = {}

    if not league_maturity.insight_is_available(
        "trade_tendencies", maturity_context
    ):
        if show_header:
            workspace_ui.render_section_header(
                "Manager Tendencies",
                kicker="Behavior Pattern",
                note="Historical behavior unlocks only after repeated completed trades.",
                compact=compact,
            )
        st.info(
            league_maturity.evidence_status(
                "trade_tendencies", maturity_context
            )["message"]
        )
        return
    if not _safe_text(team.get("trading_style")):
        return

    if show_header:
        workspace_ui.render_section_header(
            "Manager Tendencies",
            kicker="Behavior Pattern",
            note="Built from completed transactions, current roster shape, draft capital, and current team direction.",
            compact=compact,
        )
    workspace_ui.render_summary_tiles(
        [
            {
                "label": "Trading Style",
                "value": _safe_text(team.get("trading_style"), "Unknown"),
                "note": _safe_text(team.get("manager_trade_implication")),
                "tone": "power",
            },
            {
                "label": "Roster Philosophy",
                "value": _safe_text(
                    team.get("roster_philosophy"),
                    "Balanced",
                ),
                "note": "Current roster age, strategy, and rank shape.",
                "tone": "franchise",
            },
            {
                "label": "Asset Behavior",
                "value": _safe_text(
                    team.get("asset_behavior"),
                    "Balanced Asset Manager",
                ),
                "note": "Current pick position and trade history tendencies.",
                "tone": "opportunity",
            },
            {
                "label": "Activity",
                "value": _safe_text(
                    team.get("activity_level"),
                    "Average Activity",
                ),
                "note": _safe_text(team.get("manager_tendencies_summary")),
                "tone": "strategy",
            },
        ]
    )
    workspace_ui.render_analysis_cards(
        [
            {
                "label": "Evidence",
                "title": "Why the model sees it this way",
                "items": list(team.get("manager_evidence") or []),
                "tone": "strength",
            },
            {
                "label": "Trade Implication",
                "title": "How to approach this manager",
                "items": [
                    _safe_text(
                        team.get("manager_trade_implication"),
                        "No trade implication available yet.",
                    )
                ],
                "tone": "opportunity",
            },
        ]
    )


def render_league_team_page_header(
    team_profile: dict,
    selected_league_name: str,
    *,
    team_logo_html: Callable,
):
    team_name = _safe_text(team_profile.get("team_name"), "Team")
    avatar_url = _safe_text(team_profile.get("avatar_url"))
    username = owner_handle(
        team_profile.get("username"),
        team_profile.get("owner_name"),
    )
    owner_name = _safe_text(team_profile.get("owner_name"))
    league = _safe_text(selected_league_name, "Selected league")
    owner_meta = (
        owner_name
        if owner_name and username.replace("@", "") != owner_name
        else "Sleeper owner"
    )
    logo_html = team_logo_html(avatar_url, team_name)
    html = f"""
    <div class="team-identity-card league-team-page">
        <div class="league-team-header">
            {logo_html}
            <div class="league-team-copy">
                <div class="team-kicker">{escape(league)}</div>
                <div class="team-name">{escape(team_name)}</div>
                <div class="team-owner-handle">{escape(username)}</div>
                <div class="team-owner-meta">{escape(owner_meta)}</div>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_league_team_workspace(
    *,
    team_profile: dict,
    selected_league_name: str,
    selected_team_summary: dict,
    selected_draft_row: dict,
    team_metrics: dict,
    league_size: int,
    is_my_roster_page: bool,
    selected_league_id: str,
    selected_roster_id,
    health_label: str,
    injured_starters: int,
    key_injuries: str,
    advice_items: list[dict],
    starters: pd.DataFrame,
    bench: pd.DataFrame,
    starters_display: pd.DataFrame,
    bench_display: pd.DataFrame,
    team_pick_rows: list[dict],
    team_players: pd.DataFrame,
    roster_table: pd.DataFrame,
    roster_score_field: str,
    team_logo_html: Callable,
    format_score: Callable,
    format_rank: Callable,
    render_summary_tiles: Callable,
    render_workspace_handoff: Callable,
    render_team_score_details: Callable,
    render_advice_cards: Callable,
    render_player_scan_cards: Callable,
    team_needs_assessment: TeamNeedsAssessment | None = None,
) -> None:
    render_league_team_page_header(
        team_profile,
        selected_league_name,
        team_logo_html=team_logo_html,
    )
    render_team_rank_cards(selected_team_summary)
    render_archetype_summary(selected_team_summary, compact=True)
    render_manager_tendencies_summary(selected_team_summary, compact=True)
    need_presentation = build_team_need_presentation(
        team_metrics,
        team_needs_assessment,
    )
    render_summary_tiles(
        [
            {
                "label": "Strongest Room",
                "value": " / ".join((team_metrics or {}).get("strengths", [])[:2]) or "Balanced",
                "note": "Best scoring leverage on the roster right now.",
                "tone": "power",
            },
            {
                "label": need_presentation["headline_label"],
                "value": need_presentation["headline_value"],
                "note": need_presentation["headline_note"],
                "tone": "weakness",
            },
            {
                "label": "Health",
                "value": health_label or (
                    "Injury Data Uncertain"
                    if _safe_text(selected_team_summary.get("injury_data_quality"), "available")
                    != "available"
                    else "No meaningful injury concern"
                ),
                "note": (
                    _safe_text(
                        selected_team_summary.get("actionable_injury_summary")
                        or selected_team_summary.get("injury_data_note")
                    )
                    or f"Value-weighted impact {format_score(selected_team_summary.get('injury_impact_score'))}"
                ),
                "tone": "risk",
            },
            {
                "label": "Draft Capital",
                "value": format_rank(selected_draft_row.get("draft_capital_rank")),
                "note": f"{format_score(selected_draft_row.get('draft_capital'))} total | {int(selected_draft_row.get('pick_count') or 0)} picks",
                "tone": "franchise",
            },
        ]
    )
    if is_my_roster_page:
        render_workspace_handoff(
            key_prefix=f"league_team_my_team_{selected_league_id}_{selected_roster_id}",
            route_key="my_team",
            button_label="Open My Team",
            note="My Team owns daily roster decisions for your roster. Teams keeps this view focused on league comparison context only.",
            tone="info",
        )
    else:
        render_summary_tiles(
            build_team_partner_context_tiles(
                selected_team_summary,
                team_metrics,
                selected_draft_row,
                league_size,
                team_needs_assessment=team_needs_assessment,
            )
        )
        render_workspace_handoff(
            key_prefix=f"league_team_trade_hub_{selected_league_id}_{selected_roster_id}",
            route_key="trade_hub",
            button_label="Open Trade Hub",
            note="Use Trade Hub when you want to turn this team context into actual trade discovery.",
            tone="caption",
        )

    if health_label:
        st.warning(
            f"Health context: {health_label}"
            + (
                f" | {injured_starters} injured starter"
                f"{'s' if injured_starters != 1 else ''}."
                if injured_starters > 0
                else "."
            )
        )
    if key_injuries:
        st.caption(f"Key injuries: {key_injuries}")

    with st.expander("Detailed scores", expanded=False):
        render_team_score_details(selected_team_summary, "Franchise Score")

    if is_my_roster_page:
        return

    render_advice_cards(advice_items)
    starter_tab, bench_tab = st.tabs(["Starters", "Bench"])
    with starter_tab:
        st.markdown("#### Suggested Starters")
        render_player_scan_cards(
            starters.sort_values("value_score", ascending=False),
            score_field="value_score",
            title="Starting Lineup",
            note="Starter-weighted core for this roster under the current settings.",
            max_items=min(len(starters), 12),
            show_slot=True,
            status_label="Starter",
            extra_tags_fn=lambda row: ["Starter"],
            enable_quick_view=True,
            quick_view_source_label="League Overview - Team Starters",
            quick_view_key_prefix=f"league_team_starters_{selected_league_id}_{selected_roster_id}",
        )
        with st.expander("Full detail table", expanded=False):
            from modules import executive_table_ui

            executive_table_ui.render_executive_table_disclosure(
                starters_display.reset_index(drop=True),
                title="Starting lineup detail",
                primary_column="name" if "name" in starters_display.columns else starters_display.columns[0],
                secondary_columns=tuple(
                    column for column in ("slot", "position", "value_score") if column in starters_display.columns
                ),
                max_summary_rows=8,
                include_expander=False,
                key_suffix=f"league_team_starters_table_{selected_league_id}_{selected_roster_id}",
            )
    with bench_tab:
        st.markdown("#### Bench / Depth")
        render_player_scan_cards(
            bench.sort_values("value_score", ascending=False),
            score_field="value_score",
            title="Bench and Depth",
            note="Replacement-level strength, stash value, and contingency depth.",
            max_items=min(len(bench), 12),
            status_label="Depth",
            extra_tags_fn=lambda row: ["Bench"] if _safe_text(row.get("player_tier")) in {"Depth", "Developmental"} else [],
            enable_quick_view=True,
            quick_view_source_label="League Overview - Team Bench",
            quick_view_key_prefix=f"league_team_bench_{selected_league_id}_{selected_roster_id}",
        )
        with st.expander("Full detail table", expanded=False):
            from modules import executive_table_ui

            executive_table_ui.render_executive_table_disclosure(
                bench_display.reset_index(drop=True),
                title="Bench detail",
                primary_column="name" if "name" in bench_display.columns else bench_display.columns[0],
                secondary_columns=tuple(
                    column for column in ("position", "value_score") if column in bench_display.columns
                ),
                max_summary_rows=8,
                include_expander=False,
                key_suffix=f"league_team_bench_table_{selected_league_id}_{selected_roster_id}",
            )

    with st.expander("Detailed draft picks", expanded=False):
        if team_pick_rows:
            from modules import executive_table_ui

            pick_df = pd.DataFrame(team_pick_rows)
            executive_table_ui.render_executive_table_disclosure(
                pick_df,
                title="Owned picks",
                primary_column="season" if "season" in pick_df.columns else pick_df.columns[0],
                secondary_columns=tuple(
                    column for column in ("round", "pick", "value") if column in pick_df.columns
                ),
                max_summary_rows=10,
                include_expander=False,
                key_suffix=f"league_team_picks_{selected_league_id}_{selected_roster_id}",
            )
        else:
            st.caption("No tracked future picks for this roster.")

    st.markdown("#### Full Roster")
    render_player_scan_cards(
        team_players,
        score_field=roster_score_field,
        title="Roster Scan",
        note="Best mobile view for full-roster value, opportunity, and injury context.",
        max_items=min(len(team_players), 14),
        enable_quick_view=True,
        quick_view_source_label="League Overview - Team Roster",
        quick_view_key_prefix=f"league_team_roster_{selected_league_id}_{selected_roster_id}",
    )
    with st.expander("Full detail table", expanded=False):
        from modules import executive_table_ui

        executive_table_ui.render_executive_table_disclosure(
            roster_table.reset_index(drop=True),
            title="Full roster detail",
            primary_column="name" if "name" in roster_table.columns else roster_table.columns[0],
            secondary_columns=tuple(
                column for column in ("position", "value_score", "player_tier") if column in roster_table.columns
            ),
            max_summary_rows=10,
            include_expander=False,
            key_suffix=f"league_team_roster_table_{selected_league_id}_{selected_roster_id}",
        )
