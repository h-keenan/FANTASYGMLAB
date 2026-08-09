"""Canonical player overall/position ranks by scoring format.

Presentation and consistency only. Ranking order uses the existing
format-adjusted valuation score already produced by the valuation lens —
this module does not invent a new ranking formula, change valuations,
recommendations, Trust, trade, or waiver logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, MutableMapping

import pandas as pd

# Customer-facing format ids. Half-PPR is supported because league settings
# and valuation multipliers already resolve it from Sleeper reception scoring.
FORMAT_PPR = "PPR"
FORMAT_HALF_PPR = "Half-PPR"
FORMAT_STANDARD = "Standard"
SUPPORTED_SCORING_FORMATS = (FORMAT_PPR, FORMAT_HALF_PPR, FORMAT_STANDARD)

# Internal aliases accepted when resolving league settings.
_FORMAT_ALIASES = {
    "ppr": FORMAT_PPR,
    "full-ppr": FORMAT_PPR,
    "full_ppr": FORMAT_PPR,
    "half-ppr": FORMAT_HALF_PPR,
    "half_ppr": FORMAT_HALF_PPR,
    "half ppr": FORMAT_HALF_PPR,
    "0.5 ppr": FORMAT_HALF_PPR,
    "standard": FORMAT_STANDARD,
    "std": FORMAT_STANDARD,
    "non-ppr": FORMAT_STANDARD,
    "non_ppr": FORMAT_STANDARD,
    "nonppr": FORMAT_STANDARD,
}

RANK_SOURCE = "format_adjusted_valuation_order"
RANK_METHODOLOGY = (
    "Players are ordered by the existing format-adjusted dynasty/value score "
    "already produced for the active league scoring settings. Overall and "
    "position ranks are dense ranks within the eligible skill-position pool."
)
RANKABLE_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})

OVERALL_RANK_COLUMN = "overall_rank"
POSITION_RANK_COLUMN = "position_rank"
CANONICAL_OVERALL_COLUMN = "canonical_overall_rank"
CANONICAL_POSITION_COLUMN = "canonical_position_rank"
RANK_FORMAT_COLUMN = "rank_scoring_format"
RANK_VERSION_COLUMN = "rank_version"
RANK_GENERATED_AT_COLUMN = "rank_generated_at"
RANK_SOURCE_COLUMN = "rank_source"
RANK_UNAVAILABLE_COLUMN = "rank_unavailable_reason"


@dataclass(frozen=True)
class ScoringRankContext:
    """Resolved scoring format used for customer-facing ranks."""

    scoring_format: str
    supported: bool
    source: str
    fallback_label: str = ""
    unsupported_reason: str = ""

    @property
    def display_format(self) -> str:
        if self.supported:
            return self.scoring_format
        return self.fallback_label or "Unsupported scoring"


@dataclass(frozen=True)
class CanonicalPlayerRank:
    """One player's ranks for one scoring format."""

    player_id: str
    scoring_format: str
    overall_rank: int | None
    position_rank: int | None
    position: str
    season: str
    ranking_version: str
    source_provenance: str
    generated_at: str
    unavailable_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def available(self) -> bool:
        return self.overall_rank is not None and not self.unavailable_reason


@dataclass(frozen=True)
class CanonicalRankingTable:
    """In-memory ranking table for one scoring format."""

    scoring_format: str
    season: str
    ranking_version: str
    source_provenance: str
    generated_at: str
    score_field: str
    rows: tuple[CanonicalPlayerRank, ...]

    def by_player_id(self) -> dict[str, CanonicalPlayerRank]:
        return {row.player_id: row for row in self.rows if row.player_id}


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


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_scoring_format(value: object) -> str | None:
    """Return a supported format id or None when unsupported/unknown."""

    text = _text(value)
    if not text:
        return None
    if text in SUPPORTED_SCORING_FORMATS:
        return text
    return _FORMAT_ALIASES.get(text.casefold())


def resolve_scoring_rank_context(
    league_settings: Mapping[str, Any] | None = None,
    *,
    override: object = None,
) -> ScoringRankContext:
    """Resolve the active ranking format from league settings / override.

    Fallback behavior (documented):
    - Explicit override in {PPR, Half-PPR, Standard} wins (source=manual).
    - Else use league_settings['scoring_format'] when supported (source from
      settings provenance or 'league').
    - Unknown/custom formats are unsupported: ranks are unavailable and must
      not silently reuse another format's ranks.
    """

    override_text = _text(override)
    if override_text and override_text.casefold() not in {"auto"}:
        override_format = normalize_scoring_format(override_text)
        if override_format:
            return ScoringRankContext(
                scoring_format=override_format,
                supported=True,
                source="manual",
            )
        return ScoringRankContext(
            scoring_format=override_text,
            supported=False,
            source="manual",
            fallback_label=override_text,
            unsupported_reason=(
                f"Scoring format '{override_text}' is not a verified ranking format. "
                "Ranks are unavailable rather than silently falling back."
            ),
        )

    settings = dict(league_settings or {})
    raw_format = settings.get("scoring_format")
    normalized = normalize_scoring_format(raw_format)
    sources = settings.get("_sources") if isinstance(settings.get("_sources"), Mapping) else {}
    source = _text((sources or {}).get("scoring_format"), "league") or "league"
    if normalized:
        return ScoringRankContext(
            scoring_format=normalized,
            supported=True,
            source=source,
        )

    raw_text = _text(raw_format, "unknown")
    return ScoringRankContext(
        scoring_format=raw_text,
        supported=False,
        source=source or "league",
        fallback_label=raw_text,
        unsupported_reason=(
            f"Scoring format '{raw_text}' is not a verified ranking format. "
            "Ranks are unavailable rather than silently falling back."
        ),
    )


def ranking_version_for(
    *,
    scoring_format: str,
    season: object = "",
    score_field: str = "dynasty_score",
) -> str:
    season_text = _text(season) or "current"
    return f"{season_text}:{scoring_format}:{score_field}:{RANK_SOURCE}"


def _eligible_mask(frame: pd.DataFrame) -> pd.Series:
    positions = (
        frame.get("position", pd.Series("", index=frame.index))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    eligible = positions.isin(RANKABLE_POSITIONS)
    if "player_eligible" in frame.columns:
        eligible = eligible & frame["player_eligible"].fillna(False).astype(bool)
    elif "active" in frame.columns:
        active = frame["active"]
        if active.dtype == object:
            active_bool = active.map(
                lambda value: str(value).strip().casefold()
                in {"1", "true", "yes", "y", "active"}
                if value is not None and not (isinstance(value, float) and pd.isna(value))
                else False
            )
        else:
            active_bool = active.fillna(False).astype(bool)
        eligible = eligible & active_bool
    status = (
        frame.get("status", pd.Series("", index=frame.index))
        .fillna("")
        .astype(str)
        .str.casefold()
    )
    eligible = eligible & ~status.isin({"retired", "inactive", "not active", "excused"})
    return eligible


def build_canonical_ranking_table(
    players: pd.DataFrame,
    *,
    scoring_format: str,
    score_field: str = "dynasty_score",
    season: object = "",
    generated_at: str | None = None,
    context: ScoringRankContext | None = None,
) -> CanonicalRankingTable:
    """Build ranks for one verified scoring format from existing scores."""

    format_id = normalize_scoring_format(scoring_format) or _text(scoring_format)
    generated = generated_at or utc_now_iso()
    season_text = _text(season) or "current"
    version = ranking_version_for(
        scoring_format=format_id,
        season=season_text,
        score_field=score_field,
    )

    empty_table = CanonicalRankingTable(
        scoring_format=format_id,
        season=season_text,
        ranking_version=version,
        source_provenance=RANK_SOURCE,
        generated_at=generated,
        score_field=score_field,
        rows=(),
    )

    if context is not None and not context.supported:
        if players is None or players.empty:
            return empty_table
        rows = tuple(
            CanonicalPlayerRank(
                player_id=_text(row.get("player_id")),
                scoring_format=format_id,
                overall_rank=None,
                position_rank=None,
                position=_text(row.get("position")).upper(),
                season=season_text,
                ranking_version=version,
                source_provenance=RANK_SOURCE,
                generated_at=generated,
                unavailable_reason=context.unsupported_reason
                or "Scoring format is not supported for verified ranks.",
            )
            for _, row in players.iterrows()
            if _text(row.get("player_id"))
        )
        return CanonicalRankingTable(
            scoring_format=format_id,
            season=season_text,
            ranking_version=version,
            source_provenance=RANK_SOURCE,
            generated_at=generated,
            score_field=score_field,
            rows=rows,
        )

    if players is None or players.empty:
        return empty_table

    frame = players.copy()
    field = score_field if score_field in frame.columns else (
        "dynasty_score" if "dynasty_score" in frame.columns else "value_score"
    )
    if field not in frame.columns:
        rows = tuple(
            CanonicalPlayerRank(
                player_id=_text(row.get("player_id")),
                scoring_format=format_id,
                overall_rank=None,
                position_rank=None,
                position=_text(row.get("position")).upper(),
                season=season_text,
                ranking_version=version,
                source_provenance=RANK_SOURCE,
                generated_at=generated,
                unavailable_reason="Rank unavailable: no verified score field on player row.",
            )
            for _, row in frame.iterrows()
            if _text(row.get("player_id"))
        )
        return CanonicalRankingTable(
            scoring_format=format_id,
            season=season_text,
            ranking_version=version,
            source_provenance=RANK_SOURCE,
            generated_at=generated,
            score_field=score_field,
            rows=rows,
        )

    frame["_rank_score"] = pd.to_numeric(frame[field], errors="coerce")
    frame["_player_id"] = frame.get("player_id", pd.Series("", index=frame.index)).map(
        lambda value: _text(value)
    )
    frame["_position"] = (
        frame.get("position", pd.Series("", index=frame.index))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    eligible = _eligible_mask(frame) & frame["_player_id"].ne("") & frame["_rank_score"].notna()
    ranked = (
        frame.loc[eligible]
        .sort_values(
            ["_rank_score", "_player_id"],
            ascending=[False, True],
            kind="stable",
        )
        .copy()
    )
    ranked["overall_rank"] = range(1, len(ranked) + 1)
    ranked["position_rank"] = ranked.groupby("_position", sort=False).cumcount() + 1

    by_id = {
        _text(row["_player_id"]): CanonicalPlayerRank(
            player_id=_text(row["_player_id"]),
            scoring_format=format_id,
            overall_rank=int(row["overall_rank"]),
            position_rank=int(row["position_rank"]),
            position=_text(row["_position"]).upper(),
            season=season_text,
            ranking_version=version,
            source_provenance=RANK_SOURCE,
            generated_at=generated,
            unavailable_reason="",
        )
        for _, row in ranked.iterrows()
    }

    rows_list: list[CanonicalPlayerRank] = []
    for idx, row in frame.iterrows():
        player_id = _text(row.get("_player_id") or row.get("player_id"))
        if not player_id:
            continue
        if player_id in by_id:
            rows_list.append(by_id[player_id])
            continue
        reason = "Rank unavailable"
        try:
            if not bool(_eligible_mask(frame.loc[[idx]]).iloc[0]):
                reason = (
                    "Rank unavailable: player is inactive, retired, "
                    "or outside the skill-position pool."
                )
            elif pd.isna(row.get("_rank_score")):
                reason = "Rank unavailable: no verified score for this player."
        except Exception:
            reason = "Rank unavailable"
        rows_list.append(
            CanonicalPlayerRank(
                player_id=player_id,
                scoring_format=format_id,
                overall_rank=None,
                position_rank=None,
                position=_text(row.get("_position") or row.get("position")).upper(),
                season=season_text,
                ranking_version=version,
                source_provenance=RANK_SOURCE,
                generated_at=generated,
                unavailable_reason=reason,
            )
        )

    return CanonicalRankingTable(
        scoring_format=format_id,
        season=season_text,
        ranking_version=version,
        source_provenance=RANK_SOURCE,
        generated_at=generated,
        score_field=field,
        rows=tuple(rows_list),
    )


def attach_canonical_ranks(
    players: pd.DataFrame,
    *,
    scoring_format: str,
    score_field: str = "dynasty_score",
    season: object = "",
    context: ScoringRankContext | None = None,
    generated_at: str | None = None,
    timing_out: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Attach canonical rank columns to a player frame (copy).

    Ranking methodology matches ``build_canonical_ranking_table`` (same eligibility,
    stable score ordering, overall + positional ranks). This path avoids building
    thousands of ``CanonicalPlayerRank`` dataclasses when only frame columns are
    needed — that was the dominant ``ranks_ready`` cost on cold prepared-frame miss.
    """

    import time as _time

    def _mark(name: str, started: float) -> None:
        if timing_out is not None:
            timing_out[name] = round((_time.perf_counter() - started) * 1000, 3)

    total_started = _time.perf_counter()
    if players is None:
        return pd.DataFrame()

    format_id = normalize_scoring_format(scoring_format) or _text(scoring_format)
    generated = generated_at or utc_now_iso()
    season_text = _text(season) or "current"
    version = ranking_version_for(
        scoring_format=format_id,
        season=season_text,
        score_field=score_field,
    )
    rank_columns = (
        OVERALL_RANK_COLUMN,
        POSITION_RANK_COLUMN,
        CANONICAL_OVERALL_COLUMN,
        CANONICAL_POSITION_COLUMN,
        RANK_FORMAT_COLUMN,
        RANK_VERSION_COLUMN,
        RANK_GENERATED_AT_COLUMN,
        RANK_SOURCE_COLUMN,
        RANK_UNAVAILABLE_COLUMN,
    )

    if players.empty:
        frame = players.copy()
        for column in rank_columns:
            frame[column] = pd.Series(dtype="object")
        _mark("total_ms", total_started)
        return frame

    copy_started = _time.perf_counter()
    frame = players.copy()
    _mark("dataframe_copy_ms", copy_started)

    if context is not None and not context.supported:
        reason = (
            context.unsupported_reason
            or "Scoring format is not supported for verified ranks."
        )
        frame[CANONICAL_OVERALL_COLUMN] = None
        frame[CANONICAL_POSITION_COLUMN] = None
        frame[OVERALL_RANK_COLUMN] = None
        frame[POSITION_RANK_COLUMN] = None
        frame[RANK_FORMAT_COLUMN] = format_id
        frame[RANK_VERSION_COLUMN] = version
        frame[RANK_GENERATED_AT_COLUMN] = generated
        frame[RANK_SOURCE_COLUMN] = RANK_SOURCE
        frame[RANK_UNAVAILABLE_COLUMN] = reason
        _mark("total_ms", total_started)
        return frame

    field = score_field if score_field in frame.columns else (
        "dynasty_score" if "dynasty_score" in frame.columns else "value_score"
    )
    if field not in frame.columns:
        frame[CANONICAL_OVERALL_COLUMN] = None
        frame[CANONICAL_POSITION_COLUMN] = None
        frame[OVERALL_RANK_COLUMN] = None
        frame[POSITION_RANK_COLUMN] = None
        frame[RANK_FORMAT_COLUMN] = format_id
        frame[RANK_VERSION_COLUMN] = version
        frame[RANK_GENERATED_AT_COLUMN] = generated
        frame[RANK_SOURCE_COLUMN] = RANK_SOURCE
        frame[RANK_UNAVAILABLE_COLUMN] = (
            "Rank unavailable: no verified score field on player row."
        )
        _mark("total_ms", total_started)
        return frame

    prep_started = _time.perf_counter()
    frame["_rank_score"] = pd.to_numeric(frame[field], errors="coerce")
    frame["_player_id"] = frame.get("player_id", pd.Series("", index=frame.index)).map(
        lambda value: _text(value)
    )
    frame["_position"] = (
        frame.get("position", pd.Series("", index=frame.index))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    _mark("score_prep_ms", prep_started)

    eligible_started = _time.perf_counter()
    eligible_mask = _eligible_mask(frame)
    eligible = eligible_mask & frame["_player_id"].ne("") & frame["_rank_score"].notna()
    _mark("eligible_filter_ms", eligible_started)

    sort_started = _time.perf_counter()
    ranked = (
        frame.loc[eligible]
        .sort_values(
            ["_rank_score", "_player_id"],
            ascending=[False, True],
            kind="stable",
        )
        .copy()
    )
    ranked["overall_rank"] = range(1, len(ranked) + 1)
    ranked["position_rank"] = ranked.groupby("_position", sort=False).cumcount() + 1
    _mark("sort_and_positional_ms", sort_started)

    merge_started = _time.perf_counter()
    rank_lookup = ranked.set_index("_player_id")[["overall_rank", "position_rank"]]
    overall = frame["_player_id"].map(rank_lookup["overall_rank"])
    position = frame["_player_id"].map(rank_lookup["position_rank"])
    unavailable = pd.Series("", index=frame.index, dtype=object)
    missing = overall.isna()
    inactive = missing & ~eligible_mask
    no_score = missing & ~inactive & frame["_rank_score"].isna()
    other = missing & ~inactive & ~no_score
    unavailable.loc[inactive] = (
        "Rank unavailable: player is inactive, retired, "
        "or outside the skill-position pool."
    )
    unavailable.loc[no_score] = "Rank unavailable: no verified score for this player."
    unavailable.loc[other] = "Rank unavailable"
    unavailable.loc[frame["_player_id"].eq("")] = "Rank unavailable"

    frame[CANONICAL_OVERALL_COLUMN] = [
        (None if pd.isna(value) else int(value)) for value in overall.tolist()
    ]
    frame[CANONICAL_POSITION_COLUMN] = [
        (None if pd.isna(value) else int(value)) for value in position.tolist()
    ]
    frame[OVERALL_RANK_COLUMN] = frame[CANONICAL_OVERALL_COLUMN]
    frame[POSITION_RANK_COLUMN] = frame[CANONICAL_POSITION_COLUMN]
    frame[RANK_FORMAT_COLUMN] = format_id
    frame[RANK_VERSION_COLUMN] = version
    frame[RANK_GENERATED_AT_COLUMN] = generated
    frame[RANK_SOURCE_COLUMN] = RANK_SOURCE
    frame[RANK_UNAVAILABLE_COLUMN] = [
        (reason if missing_flag else "")
        for reason, missing_flag in zip(unavailable.tolist(), missing.tolist())
    ]
    frame.drop(columns=["_rank_score", "_player_id", "_position"], inplace=True, errors="ignore")
    _mark("merge_assign_ms", merge_started)
    _mark("total_ms", total_started)
    return frame



def lookup_player_rank(
    players: pd.DataFrame | Mapping[str, Any] | None,
    player_id: object,
) -> CanonicalPlayerRank | None:
    """Read a canonical rank from an annotated frame or row mapping."""

    pid = _text(player_id)
    if not pid:
        return None
    if isinstance(players, Mapping):
        row = players
        overall = _positive_int(
            row.get(CANONICAL_OVERALL_COLUMN, row.get(OVERALL_RANK_COLUMN))
        )
        position_rank = _positive_int(
            row.get(CANONICAL_POSITION_COLUMN, row.get(POSITION_RANK_COLUMN))
        )
        unavailable = _text(row.get(RANK_UNAVAILABLE_COLUMN))
        if overall is None and not unavailable:
            unavailable = "Rank unavailable"
        scoring_format = _text(row.get(RANK_FORMAT_COLUMN))
        return CanonicalPlayerRank(
            player_id=pid,
            scoring_format=scoring_format,
            overall_rank=overall,
            position_rank=position_rank,
            position=_text(row.get("position")).upper(),
            season=_text(row.get("stats_season") or row.get("season"), "current"),
            ranking_version=_text(row.get(RANK_VERSION_COLUMN)),
            source_provenance=_text(row.get(RANK_SOURCE_COLUMN), RANK_SOURCE),
            generated_at=_text(row.get(RANK_GENERATED_AT_COLUMN)),
            unavailable_reason=unavailable if overall is None else "",
        )
    if players is None or getattr(players, "empty", True):
        return None
    matched = players[
        players.get("player_id", pd.Series(dtype=object)).astype(str) == pid
    ]
    if matched.empty:
        return None
    return lookup_player_rank(matched.iloc[0].to_dict(), pid)


def format_compact_rank(
    overall_rank: object = None,
    position_rank: object = None,
    position: object = "",
    *,
    unavailable_reason: object = "",
) -> str:
    """Compact card label: 'OVR #12 · WR #4' or 'Rank unavailable'."""

    overall = _positive_int(overall_rank)
    pos_rank = _positive_int(position_rank)
    pos = _text(position).upper()
    if overall is None:
        return "Rank unavailable"
    parts = [f"OVR #{overall}"]
    if pos_rank and pos:
        parts.append(f"{pos} #{pos_rank}")
    return " · ".join(parts)


def format_detail_ranks(
    *,
    overall_rank: object = None,
    position_rank: object = None,
    position: object = "",
    scoring_format: object = "",
    unavailable_reason: object = "",
) -> dict[str, str]:
    """Full-detail labels for PQV / dossiers."""

    overall = _positive_int(overall_rank)
    pos_rank = _positive_int(position_rank)
    pos = _text(position).upper()
    fmt = _text(scoring_format)
    if overall is None:
        return {
            "overall": "Rank unavailable",
            "overall_display": "Rank unavailable",
            "position": "",
            "position_display": "",
            "format": fmt,
            "unavailable_reason": _text(unavailable_reason, "Rank unavailable"),
        }
    position_label = f"{pos}{pos_rank}" if pos and pos_rank else (
        f"#{pos_rank}" if pos_rank else ""
    )
    return {
        "overall": str(overall),
        "overall_display": f"#{overall}",
        "position": position_label,
        # Full detail: Position Rank: WR4 (not "#4 WR")
        "position_display": position_label,
        "format": fmt,
        "unavailable_reason": "",
    }


def format_comparison_line(
    *,
    scoring_format: str,
    overall_rank: object,
    position_rank: object,
    position: object,
) -> str:
    """One-line format comparison: 'PPR: OVR #12 · WR #4'."""

    compact = format_compact_rank(overall_rank, position_rank, position)
    return f"{_text(scoring_format, 'Format')}: {compact}"


def format_local_board_rank(rank: object, *, prefix: str = "#") -> str:
    """Draft/FA-local board numbers — never display 0 as a verified rank."""

    parsed = _positive_int(rank)
    if parsed is None:
        return "—"
    return f"{prefix}{parsed}"


def ranks_match_across_rows(rows: Iterable[Mapping[str, Any]]) -> bool:
    """True when every row reports the same canonical ranks for the same player/format."""

    normalized: list[tuple[str, str, int | None, int | None]] = []
    for row in rows:
        normalized.append(
            (
                _text(row.get("player_id")),
                _text(row.get(RANK_FORMAT_COLUMN) or row.get("scoring_format")),
                _positive_int(row.get(CANONICAL_OVERALL_COLUMN, row.get(OVERALL_RANK_COLUMN))),
                _positive_int(
                    row.get(CANONICAL_POSITION_COLUMN, row.get(POSITION_RANK_COLUMN))
                ),
            )
        )
    if not normalized:
        return True
    first = normalized[0]
    return all(item == first for item in normalized)


def invalidate_rank_columns(state: MutableMapping[str, Any], *prefixes: str) -> None:
    """Drop session keys that cache ranked boards when league/scoring context changes."""

    doomed = []
    for key in list(state.keys()):
        text = str(key)
        if "canonical_rank" in text or "rank_context" in text:
            doomed.append(key)
            continue
        for prefix in prefixes:
            if prefix and text.startswith(prefix):
                doomed.append(key)
                break
    for key in doomed:
        state.pop(key, None)


def build_format_comparison_for_player(
    player_id: object,
    base_players: pd.DataFrame,
    *,
    apply_lens,
    valuation_lens: str,
    base_league_settings: Mapping[str, Any] | None,
    score_field: str = "dynasty_score",
    formats: tuple[str, ...] = SUPPORTED_SCORING_FORMATS,
    season: object = "",
) -> dict[str, CanonicalPlayerRank]:
    """Build explicit PPR / Half-PPR / Standard ranks for one player.

    Uses the existing valuation lens with alternate scoring_format settings.
    Does not mutate the active recommendation board.
    """

    pid = _text(player_id)
    if not pid or base_players is None or base_players.empty:
        return {}
    results: dict[str, CanonicalPlayerRank] = {}
    settings_base = dict(base_league_settings or {})
    for fmt in formats:
        settings = dict(settings_base)
        settings["scoring_format"] = fmt
        valued = apply_lens(base_players.copy(), valuation_lens, settings)
        table = build_canonical_ranking_table(
            valued,
            scoring_format=fmt,
            score_field=score_field,
            season=season,
            context=ScoringRankContext(
                scoring_format=fmt,
                supported=True,
                source="comparison",
            ),
        )
        rank = table.by_player_id().get(pid)
        if rank is not None:
            results[fmt] = rank
    return results
