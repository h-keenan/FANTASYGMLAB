"""Head-to-head player comparison — web port of mobile's PlayerCompareScreen.

Mirrors mobile/src/screens/PlayerCompareScreen.tsx's buildValueRows /
buildModelRows / CompareRowView, extended to close the same PQV-parity gap
mobile's Compare screen closes: Overall Rank, the 5th (age) model subscore,
opportunity Confidence, Workload/Usage trend reads, and the Decision Fit
narrative sentence. Every value here is a column already present on the same
valued/ranked ``df_players`` frame Player Quick View reads
(app.py:render_player_quick_view_content, ~app.py:4072-4075), or a function
PQV's own backend already computes off that frame (``rankings.
recency_trend_display``, ``player_quick_view.decision_fit_narrative``) — this
module only projects and renders that data, it never computes valuation.

Two row shapes: ``CompareRow`` for a real two-number diff (win/lose pill,
mirrors mobile's numeric CompareRow), and ``TextCompareRow`` for a
categorical/narrative read (Role Trend, Usage Trend) that mobile itself
renders as a text chip rather than forcing into a numeric win/lose format —
see PlayerDetailScreen.tsx's InsightChipsRow. Decision Fit's full sentence is
prose, not a label+value pair at all, so it gets its own paragraph-pair
renderer instead of either row shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Callable, Sequence

import pandas as pd

from modules import player_quick_view
from modules import rankings as rankings_module


def _numeric(value: object) -> float | None:
    """None/NaN-safe numeric coercion — treats missing as "no value" (mobile's
    ``null``), never as zero."""

    try:
        coerced = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    except Exception:
        return None
    return None if pd.isna(coerced) else float(coerced)


def _format_plain(value: float) -> str:
    """Matches mobile's ``Math.round(v).toString()`` (Market/Opportunity/
    Scarcity/Role, and Age which mobile leaves unformatted but numeric)."""

    return str(int(round(value)))


def _format_comma(value: float) -> str:
    """Matches mobile's ``Math.round(v).toLocaleString()`` (Value Score)."""

    return f"{int(round(value)):,}"


def _format_rank(value: float) -> str:
    """Matches mobile's ``` `#${v}` ```` (Position Rank)."""

    return f"#{int(round(value))}"


def _format_percent(value: float) -> str:
    """Matches mobile ModelSection's ``` `${Math.round(v)}%` ```` (Confidence)."""

    return f"{int(round(value))}%"


@dataclass(frozen=True)
class CompareRow:
    label: str
    a: float | None
    b: float | None
    format_value: Callable[[float], str] = _format_plain
    # Only Position Rank is lower-is-better, matching mobile's
    # ``LOWER_IS_BETTER = new Set(['Position Rank'])``.
    lower_is_better: bool = False


def _row_score(row: pd.Series, score_field: str) -> float | None:
    value = row.get(score_field)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        value = row.get("value_score")
    return _numeric(value)


def _row_position_rank(row: pd.Series) -> float | None:
    value = row.get("canonical_position_rank")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        value = row.get("position_rank")
    return _numeric(value)


def _row_overall_rank(row: pd.Series) -> float | None:
    """Same fallback chain PQV's own snapshot uses (app.py ~4088/4098):
    ``canonical_overall_rank`` when the league-adjusted rank has been merged
    onto this frame, else the plain wire ``overall_rank``."""

    value = row.get("canonical_overall_rank")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        value = row.get("overall_rank")
    return _numeric(value)


def _age_metric(row: pd.Series) -> tuple[str, float | None]:
    """Matches app.py's age_metric_label/age_metric_value (~4112-4116):
    ``age_score`` when this frame carries the native composite subscore,
    else the signed ``age_penalty`` delta under a different label — never
    both, and never a value invented when neither column is present."""

    has_native = "age_score" in row.index and _numeric(row.get("age_score")) is not None
    if has_native:
        return "Age Score", _numeric(row.get("age_score"))
    return "Age Lens", _numeric(row.get("age_penalty")) if "age_penalty" in row.index else None


def _combined_age_label(label_a: str, value_a: float | None, label_b: str, value_b: float | None) -> str:
    """One shared row label for two sides whose age metric could in theory
    resolve to different labels (e.g. a native age_score for one position
    pool, a fallback age_penalty for another) — prefers whichever side
    actually has a value, so the label always names the number shown."""

    if value_a is not None:
        return label_a
    if value_b is not None:
        return label_b
    return "Age Score"


def build_value_rows(row_a: pd.Series, row_b: pd.Series, *, score_field: str) -> tuple[CompareRow, ...]:
    """Value Score / Overall Rank / Position Rank / Age — the same "how do
    these two rank" group PlayerSnapshotCard leads with on mobile Player
    Detail, doubled for a head-to-head read (mirrors
    PlayerCompareScreen.tsx's buildValueRows, plus Overall Rank — PQV's own
    Snapshot card's first field, previously missing from Compare)."""

    return (
        CompareRow(
            "Value Score",
            _row_score(row_a, score_field),
            _row_score(row_b, score_field),
            _format_comma,
        ),
        CompareRow(
            "Overall Rank",
            _row_overall_rank(row_a),
            _row_overall_rank(row_b),
            _format_rank,
            lower_is_better=True,
        ),
        CompareRow(
            "Position Rank",
            _row_position_rank(row_a),
            _row_position_rank(row_b),
            _format_rank,
            lower_is_better=True,
        ),
        CompareRow("Age", _numeric(row_a.get("age")), _numeric(row_b.get("age")), _format_plain),
    )


def build_model_rows(row_a: pd.Series, row_b: pd.Series) -> tuple[CompareRow, ...]:
    """Market / Opportunity / Scarcity / Role / Age / Confidence — the same
    six composite-model fields Player Quick View's Model Breakdown renders
    for one player (app.py ~4072-4118; mobile's ModelSection), never
    recomputed here, just placed head-to-head (mirrors
    PlayerCompareScreen.tsx's buildModelRows, plus the age subscore and
    opportunity_confidence PQV also shows that Compare previously omitted)."""

    age_label_a, age_value_a = _age_metric(row_a)
    age_label_b, age_value_b = _age_metric(row_b)
    age_label = _combined_age_label(age_label_a, age_value_a, age_label_b, age_value_b)

    return (
        CompareRow("Market", _numeric(row_a.get("market_score")), _numeric(row_b.get("market_score"))),
        CompareRow(
            "Opportunity",
            _numeric(row_a.get("opportunity_score")),
            _numeric(row_b.get("opportunity_score")),
        ),
        CompareRow(
            "Scarcity",
            _numeric(row_a.get("scarcity_score")),
            _numeric(row_b.get("scarcity_score")),
        ),
        CompareRow("Role", _numeric(row_a.get("role_score")), _numeric(row_b.get("role_score"))),
        CompareRow(age_label, age_value_a, age_value_b),
        CompareRow(
            "Confidence",
            _numeric(row_a.get("opportunity_confidence")),
            _numeric(row_b.get("opportunity_confidence")),
            _format_percent,
        ),
    )


def has_any_value(rows: Sequence[CompareRow]) -> bool:
    return any(row.a is not None or row.b is not None for row in rows)


@dataclass(frozen=True)
class TextCompareRow:
    """A categorical (never numeric) head-to-head read — Role/Usage trend
    direction, not a "which number is bigger" diff. Renders as plain text,
    no win/lose pill (mirrors mobile's InsightChipsRow, which shows these as
    text chips rather than forcing them into the numeric CompareRow shape)."""

    label: str
    a: str | None
    b: str | None


def _workload_trend_text(row: pd.Series) -> str | None:
    """Same ``workload_trend`` column app.py reads (~4120), with the same
    "Unknown" placeholder treated as "nothing to say" — never rendered as a
    real read."""

    value = row.get("workload_trend")
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "unknown":
        return None
    return text


def _usage_trend_text(row: pd.Series) -> str | None:
    """Same gated read app.py narrates via ``rankings.recency_trend_display``
    (~4124) — None when the sample is too small/the move too slight to be
    worth stating, exactly as PQV itself already decides."""

    trend = rankings_module.recency_trend_display(row)
    if not trend:
        return None
    return f"{trend['arrow']} {trend['trend_pct']:+d}% ({trend['confidence_label']})"


def build_trend_rows(row_a: pd.Series, row_b: pd.Series) -> tuple[TextCompareRow, ...]:
    """Role Trend / Usage Trend — only included when at least one side has a
    real read, same "omit rather than force a value" rule as every numeric
    row above."""

    rows: list[TextCompareRow] = []
    workload_a, workload_b = _workload_trend_text(row_a), _workload_trend_text(row_b)
    if workload_a is not None or workload_b is not None:
        rows.append(TextCompareRow("Role Trend", workload_a, workload_b))
    usage_a, usage_b = _usage_trend_text(row_a), _usage_trend_text(row_b)
    if usage_a is not None or usage_b is not None:
        rows.append(TextCompareRow("Usage Trend", usage_a, usage_b))
    return tuple(rows)


def has_any_text_value(rows: Sequence[TextCompareRow]) -> bool:
    return any(row.a is not None or row.b is not None for row in rows)


def _display(row: CompareRow, value: float | None) -> str:
    return escape(row.format_value(value)) if value is not None else "—"


def compare_row_html(row: CompareRow) -> str:
    has_both = row.a is not None and row.b is not None
    a_wins = has_both and row.a != row.b and (
        (row.a < row.b) if row.lower_is_better else (row.a > row.b)
    )
    b_wins = has_both and row.a != row.b and (
        (row.b < row.a) if row.lower_is_better else (row.b > row.a)
    )

    def cell(value: float | None, wins: bool) -> str:
        pill_class = "pqv-compare-pill pqv-compare-pill-win" if wins else "pqv-compare-pill"
        return f"<div class='pqv-compare-cell'><span class='{pill_class}'>{_display(row, value)}</span></div>"

    return (
        "<div class='pqv-compare-row'>"
        f"{cell(row.a, a_wins)}"
        f"<div class='pqv-compare-label'>{escape(row.label.upper())}</div>"
        f"{cell(row.b, b_wins)}"
        "</div>"
    )


def compare_rows_html(rows: Sequence[CompareRow]) -> str:
    return f"<div class='pqv-compare-rows'>{''.join(compare_row_html(row) for row in rows)}</div>"


def _text_cell(value: str | None) -> str:
    display = escape(value) if value else "—"
    return f"<div class='pqv-compare-cell'><span class='pqv-compare-pill pqv-compare-pill-text'>{display}</span></div>"


def text_compare_row_html(row: TextCompareRow) -> str:
    return (
        "<div class='pqv-compare-row'>"
        f"{_text_cell(row.a)}"
        f"<div class='pqv-compare-label'>{escape(row.label.upper())}</div>"
        f"{_text_cell(row.b)}"
        "</div>"
    )


def text_compare_rows_html(rows: Sequence[TextCompareRow]) -> str:
    return f"<div class='pqv-compare-rows'>{''.join(text_compare_row_html(row) for row in rows)}</div>"


def decision_fit_pair(
    players_df: pd.DataFrame | None,
    row_a: pd.Series,
    row_b: pd.Series,
) -> tuple[str | None, str | None]:
    """Both sides' Decision Fit sentence — the same real, already-computed
    read PQV's backend exposes to mobile (modules.player_quick_view.
    decision_fit_narrative; mobile's QuickViewModel.decision_fit_narrative,
    rendered in PlayerDetailScreen's ModelSection). Web's own PQV dialog does
    not currently render this field either, but it is real backend output —
    never invented here — so Compare surfacing it closes a real gap rather
    than adding anything new."""

    return (
        player_quick_view.decision_fit_narrative(players_df, row_a),
        player_quick_view.decision_fit_narrative(players_df, row_b),
    )


def narrative_block_html(name_a: str, text_a: str | None, name_b: str, text_b: str | None) -> str:
    """Side-by-side prose block — Decision Fit is a full sentence, not a
    label+value pair, so it never fits CompareRow/TextCompareRow's grid; this
    renders as its own two-column paragraph pair instead. Returns "" (render
    nothing, not an empty shell) when neither side has a sentence."""

    if not text_a and not text_b:
        return ""

    def _column(name: str, text: str | None) -> str:
        body = escape(text) if text else "No decision-fit read available yet."
        return (
            "<div class='pqv-compare-narrative-col'>"
            f"<div class='pqv-compare-narrative-name'>{escape(name or 'Player')}</div>"
            f"<p class='pqv-compare-narrative-text'>{body}</p>"
            "</div>"
        )

    return (
        "<div class='pqv-compare-narrative'>"
        f"{_column(name_a, text_a)}"
        f"{_column(name_b, text_b)}"
        "</div>"
    )
