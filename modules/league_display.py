import pandas as pd

def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def _safe_positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _format_score(value) -> str:
    try:
        return f"{int(round(float(value))):,}"
    except Exception:
        return "0"


def _format_rank(value, *, tied: bool = False) -> str:
    """"#4" for a rank unique to one team, "T4" when 2+ teams share that
    exact dense rank (see modules.league_rankings.add_rank_tie_metadata,
    which computes the `<field>_tied` flag callers pass in as `tied`)."""

    try:
        rank = int(round(float(value)))
    except Exception:
        return "N/A"
    if rank <= 0:
        return "N/A"
    return f"T{rank}" if tied else f"#{rank}"


def _truncate_text(value: str, limit: int = 110) -> str:
    text = _safe_text(value).strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "..."


def tidy_label(value):
    if not isinstance(value, str):
        return str(value)
    return value.replace("_", " ").title()


def league_score_label(score_field: str) -> str:
    if score_field == "dynasty_score":
        return "Dynasty Score"
    if score_field == "rebuild_score":
        return "Rebuild Score"
    return "Value Score"
