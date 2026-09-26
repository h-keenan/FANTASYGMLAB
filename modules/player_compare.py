"""Head-to-head player comparison — web port of mobile's PlayerCompareScreen.

Mirrors mobile/src/screens/PlayerCompareScreen.tsx's buildValueRows /
buildModelRows / CompareRowView exactly: same two row groups, same fields,
same "which real number is bigger" winner highlight (never a synthesized
compare score). Every value here is a column already present on the same
valued/ranked ``df_players`` frame Player Quick View reads
(app.py:render_player_quick_view_content, ~app.py:4072-4075) — this module
only projects and renders those columns, it never computes valuation.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Callable, Sequence

import pandas as pd


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


def build_value_rows(row_a: pd.Series, row_b: pd.Series, *, score_field: str) -> tuple[CompareRow, ...]:
    """Value Score / Position Rank / Age — the same "how do these two rank"
    trio PlayerSnapshotCard leads with on mobile Player Detail, doubled for a
    head-to-head read (mirrors PlayerCompareScreen.tsx's buildValueRows)."""

    return (
        CompareRow(
            "Value Score",
            _row_score(row_a, score_field),
            _row_score(row_b, score_field),
            _format_comma,
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
    """Market / Opportunity / Scarcity / Role — the same four composite
    subscores the Model grid already renders elsewhere on Player Quick View
    (app.py ~4072-4075), never recomputed here, just placed head-to-head
    (mirrors PlayerCompareScreen.tsx's buildModelRows)."""

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
    )


def has_any_value(rows: Sequence[CompareRow]) -> bool:
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
