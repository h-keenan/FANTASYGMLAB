"""What a Trade Analyzer verdict assumed, in plain words.

A verdict is only as trustworthy as the assumptions the reader can see. This
module is a pure, read-only description of the inputs the engine already used
(league format and scoring, valuation lens, team posture, whether weekly
projections fed the lineup model, and how injury timing is estimated). It
never changes a verdict and does no valuation math; every value comes from the
same objects the endpoint already holds, and the injury defaults are read from
modules.trade_grade so the text cannot drift from what is actually applied.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from modules import team_eval, trade_grade

# Display order and labels for the lineup model's per-player estimate sources
# (modules.trade_lineup_model basis_counts keys).
_BASIS_LABELS = (
    ("projection", "weekly projections"),
    ("season_average", "season averages"),
    ("value_estimate", "value-derived estimates"),
)
_INJURY_DISPLAY = (("questionable", "Questionable"), ("doubtful", "Doubtful"), ("out", "Out"), ("ir", "IR"))


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _format_value(settings: Mapping[str, Any]) -> tuple[str, str]:
    """('Superflex, PPR, TE premium', source) from detected league settings."""

    parts: list[str] = []
    qb_format = _clean(settings.get("qb_format")) or "1QB"
    parts.append("Superflex" if qb_format.lower().startswith("super") else qb_format)
    scoring = _clean(settings.get("scoring_format"))
    if scoring:
        parts.append(scoring)
    if settings.get("te_premium"):
        parts.append("TE premium")
    sources = settings.get("_sources") if isinstance(settings.get("_sources"), Mapping) else {}
    detected = any(_clean(sources.get(key)).lower() not in ("", "default") for key in ("qb_format", "scoring_format", "te_premium"))
    return ", ".join(parts), "your league settings" if detected else "defaults (settings not detected)"


def _weeks(value: float) -> str:
    return f"{value:g}"


def _injury_timing() -> str:
    defaults = trade_grade.INJURY_STATUS_DEFAULT_WEEKS
    shown = [f"{label} {_weeks(defaults[key])}" for key, label in _INJURY_DISPLAY if key in defaults]
    return f"estimated by designation ({', '.join(shown)} weeks), not from return dates"


def _lineup_basis(lineup_model: Mapping[str, Any] | None) -> str:
    counts = lineup_model.get("basis_counts") if isinstance(lineup_model, Mapping) else None
    if isinstance(counts, Mapping):
        used = [label for key, label in _BASIS_LABELS if counts.get(key)]
        if used:
            return "lineup impact from " + ", ".join(used)
    return "values only, no weekly projections"


def build_verdict_assumptions(
    *,
    lens: str,
    settings: Mapping[str, Any] | None,
    strategy: str,
    keeper_adjusted: bool = False,
    has_picks: bool = False,
    lineup_model: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """JSON-ready ``{"line": str, "items": [{key, label, value}]}``.

    ``lineup_model`` is the verdict's optional weekly lineup model (None in the
    offseason or when the model did not run), which decides whether the basis
    line says projections or values only.
    """

    settings = settings or {}
    format_text, format_source = _format_value(settings)
    posture = team_eval.team_strategy_label(strategy)
    basis = _lineup_basis(lineup_model)
    injury = _injury_timing()
    items = [
        {"key": "format", "label": "League format", "value": f"{format_text} (from {format_source})"},
        {"key": "lens", "label": "Valuation lens", "value": _clean(lens) or "Dynasty"},
        {"key": "posture", "label": "Team posture", "value": posture},
        {"key": "basis", "label": "Basis", "value": basis},
        {"key": "injury", "label": "Injury timing", "value": injury},
    ]
    if keeper_adjusted:
        items.append({"key": "keepers", "label": "Keepers", "value": "estimated keeper surplus included"})
    if has_picks:
        items.append({"key": "picks", "label": "Draft picks", "value": "valued at your league's projected pick position"})
    line = f"Assumed: {format_text}, {_clean(lens) or 'Dynasty'} values, {posture} posture; {basis}; injury timing {injury}."
    return {"line": line, "items": items}
