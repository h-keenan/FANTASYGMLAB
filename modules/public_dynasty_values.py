"""Public, league-agnostic dynasty value board for the SEO pages.

Backs ``GET /v1/public/dynasty-values`` (no auth): the top fantasy players
valued under FantasyDesk's *default* settings (12-team PPR dynasty, 1QB or
Superflex). Nothing here reads a user, a saved league, a roster, or an
account -- the only inputs are the shared player table and the two fixed
settings profiles below, so the payload is safe to serve anonymously and to
cache aggressively.

Honesty rules (the pages built on this must never show invented data):
- A player with no usable score, no name or no position is dropped.
- ``trend`` is the model's own ``workload_trend`` label, or ``None``.
- If the source table is missing/empty the builder returns ``None`` and the
  endpoint answers 503; it never fabricates a board.
"""

from __future__ import annotations

import copy
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from modules import canonical_player_ranking, league_value_settings, player_eligibility, player_quick_view, rankings

FORMATS = ("1qb", "superflex")
POSITIONS = ("QB", "RB", "WR", "TE")
LENS = "Dynasty"
MAX_PLAYERS = 300
MAX_PER_POSITION = 60
CACHE_TTL_SECONDS = 600

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def settings_for_format(fmt: str, tep: bool = False) -> dict[str, Any]:
    settings = copy.deepcopy(league_value_settings.DEFAULT_LEAGUE_VALUE_SETTINGS)
    if tep:
        # Tight-end premium (the app's own te_premium valuation setting).
        settings["te_premium"] = True
    if fmt == "superflex":
        settings["qb_format"] = "Superflex"
        settings["superflex_count"] = 1
        settings["flex_count"] = int(settings.get("flex_count", 2)) + 1
    return settings


def _clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _int_or_none(value: Any) -> int | None:
    value = _clean(value)
    try:
        return int(round(float(value))) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text_or_none(value: Any) -> str | None:
    value = _clean(value)
    text = str(value).strip() if value is not None else ""
    return text or None


def build_public_dynasty_values(
    players_df: pd.DataFrame | None, fmt: str, *, source_updated_at: float | None = None, tep: bool = False
) -> dict[str, Any] | None:
    """Pure builder (no I/O): value board from an already-loaded players frame."""

    if fmt not in FORMATS or players_df is None or players_df.empty:
        return None
    frame = player_eligibility.filter_current_fantasy_players(players_df, surface="public_dynasty_values")
    if frame is None or frame.empty:
        return None
    frame = frame[frame["position"].isin(POSITIONS)]
    if frame.empty:
        return None

    settings = settings_for_format(fmt, tep)
    valued = league_value_settings.apply_valuation_lens(frame, LENS, settings)
    if valued is None or valued.empty:
        return None
    score_field = league_value_settings.valuation_score_field(LENS)
    context = canonical_player_ranking.resolve_scoring_rank_context(settings)
    ranked = canonical_player_ranking.attach_canonical_ranks(
        valued, scoring_format=context.scoring_format, score_field=score_field, context=context
    )
    ranked["_ovr"] = player_quick_view.overall_ratings_for_pool(ranked, score_column=score_field)
    ranked = ranked.sort_values(score_field, ascending=False)

    rows: list[dict[str, Any]] = []
    for _, row in ranked.iterrows():
        score = _int_or_none(row.get(score_field))
        name = _text_or_none(row.get("name"))
        position = _text_or_none(row.get("position"))
        pid = _text_or_none(row.get("player_id"))
        overall = _int_or_none(row.get("canonical_overall_rank"))
        pos_rank = _int_or_none(row.get("canonical_position_rank"))
        if not (score and score > 0 and name and position and pid and overall and pos_rank):
            continue
        age = _clean(row.get("age"))
        rows.append(
            {
                "player_id": pid,
                "name": name,
                "position": position,
                "team": _text_or_none(row.get("team")),
                "age": round(float(age), 1) if isinstance(age, (int, float)) and age > 0 else None,
                "years_exp": _int_or_none(row.get("years_exp")),
                "status": _text_or_none(row.get("status")),
                "injury_status": _text_or_none(row.get("injury_status")),
                "score": score,
                "overall_rank": overall,
                "position_rank": pos_rank,
                "tier": _text_or_none(row.get("player_tier")),
                "overall_rating": _int_or_none(row.get("_ovr")),
                "trend": _text_or_none(row.get("workload_trend")),
            }
        )
    # Top MAX_PLAYERS overall, plus the top MAX_PER_POSITION at every position so
    # thin positions (TE) still get a full positional board.
    rows = [r for i, r in enumerate(rows) if i < MAX_PLAYERS or r["position_rank"] <= MAX_PER_POSITION]
    if not rows:
        return None

    now = datetime.now(timezone.utc)
    updated = (
        datetime.fromtimestamp(source_updated_at, timezone.utc) if source_updated_at else now
    )
    return {
        "ok": True,
        "format": fmt,
        "tep": bool(tep),
        "scoring": "PPR",
        "teams": 12,
        "lens": LENS,
        "generated_at": now.isoformat(),
        "source_updated_at": updated.isoformat(),
        "players": rows,
    }


def get_public_dynasty_values(db_path: str, fmt: str, tep: bool = False) -> dict[str, Any] | None:
    """Cached front door: loads the shared players table and builds the board."""

    if fmt not in FORMATS:
        return None
    key = f"{db_path}:{fmt}:{'tep' if tep else 'std'}"
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    players_df = rankings.load_players(db_path)
    try:
        mtime = os.path.getmtime(db_path)
    except OSError:
        mtime = None
    payload = build_public_dynasty_values(players_df, fmt, source_updated_at=mtime, tep=tep)
    if payload is not None:
        with _cache_lock:
            _cache[key] = (now, payload)
    return payload
