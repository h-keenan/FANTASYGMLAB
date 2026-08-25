"""Presentation projection for canonical news-derived injury attention."""

from __future__ import annotations

from typing import Any, Callable, Mapping

import pandas as pd

from modules.player_identity import normalize_player_id


def annotate_player_frame(
    frame: pd.DataFrame,
    attention_by_player: Mapping[str, Mapping[str, Any]],
    *,
    has_structured_injury: Callable[[Any], bool],
) -> pd.DataFrame:
    """Return an isolated frame with pending attention, never official status."""

    annotated = frame.copy()
    annotated["injury_attention_label"] = ""
    annotated["injury_attention_pending"] = False
    annotated["injury_attention_severity"] = ""
    if annotated.empty or "player_id" not in annotated.columns:
        return annotated
    indexed = {
        normalize_player_id(player_id): payload
        for player_id, payload in (attention_by_player or {}).items()
        if normalize_player_id(player_id)
    }
    for index, row in annotated.iterrows():
        player_id = normalize_player_id(row.get("player_id"))
        attention = indexed.get(player_id)
        if not isinstance(attention, Mapping) or has_structured_injury(row):
            continue
        annotated.at[index, "injury_attention_label"] = str(
            attention.get("label") or "Injury Alert"
        )
        annotated.at[index, "injury_attention_pending"] = bool(
            attention.get("status_pending", True)
        )
        annotated.at[index, "injury_attention_severity"] = str(
            attention.get("severity") or ""
        )
    return annotated
