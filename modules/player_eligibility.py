from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np
import pandas as pd

from modules import trust_enforcement as _trust_enforcement
from modules import trust_engine as _trust_engine
from modules.trust_enforcement import EnforcementLevel, enforce_player_record
from modules.trust_engine import canonical_object_key


FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
INELIGIBLE_STATUS_TERMS = {
    "retired",
    "inactive",
    "not active",
    "historical",
    "historical only",
    "deceased",
    "invalid",
}
CURRENT_STATUS_TERMS = {
    "active",
    "free agent",
    "free_agent",
    "unsigned",
    "practice squad",
    "injured reserve",
    "ir",
    "pup",
    "nfi",
    "out",
    "questionable",
    "doubtful",
}
# Genuine injured-reserve-type designations — a team still holds this
# player's rights, he's a real dynasty asset, and Sleeper's player feed
# routinely reports `active: false` for exactly these players (their IR
# placement means they're off the active 53-man roster) even though the
# status itself is explicitly a CURRENT_STATUS_TERMS entry. See
# RESERVE_STATUS_TERMS usage in player_eligibility() below. "pup"/"nfi" are
# abbreviations that never actually appear in Sleeper's real player feed —
# confirmed against the real raw feed (data/sleeper_players.json), Sleeper
# always sends the spelled-out "Physically Unable to Perform"/"Non Football
# Injury" status text, so both must be listed alongside the abbreviations or
# this set never matches a real PUP/NFI player and the comment above's
# "fall through instead of auto-disqualifying" intent silently never fires
# for them (coridian_, 2026-10-19: "fix player identity joins... no
# mismatched profiles" — this was one real cause).
RESERVE_STATUS_TERMS = {
    "injured reserve",
    "ir",
    "pup",
    "nfi",
    "physically unable to perform",
    "non football injury",
    "non-football injury",
}
FREE_AGENT_TEAM_MARKERS = {"", "FA", "FREE AGENT", "FREE_AGENT", "NONE", "N/A", "NA"}
NEWS_FRESHNESS_DAYS = 730
UNSIGNED_VETERAN_NEWS_FRESHNESS_DAYS = 180
VETERAN_UNSIGNED_MIN_EXPERIENCE = 10
VETERAN_UNSIGNED_MIN_AGE = 35
PLAYER_ELIGIBILITY_CONTRACT_VERSION = "active-fantasy-player-v2"
TRUST_ANNOTATION_COLUMNS = {
    "is_current_fantasy_eligible",
    "player_eligibility_reason",
    "trust_enforcement",
    "trust_evidence_confidence",
    "trust_block_reason",
    "trust_validation_fingerprint",
}
TRUST_PLAYER_INPUT_COLUMNS = (
    "player_id",
    "name",
    "full_name",
    "first_name",
    "last_name",
    "position",
    "fantasy_positions",
    "sport",
    "active",
    "status",
    "team",
    "depth_chart_position",
    "depth_chart_order",
    "years_exp",
    "stats_season",
    "latest_stats_season",
    "fantasycalc_value",
    "news_updated",
    "news_updated_at",
    "metadata_updated_at",
    "updated_at",
    "age",
    "bye_week",
    "verified_signals",
)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "active"}:
        return True
    if text in {"0", "false", "no", "n", "inactive"}:
        return False
    try:
        return bool(int(float(text)))
    except (TypeError, ValueError):
        return None


def _safe_number(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if pd.notna(number) else default


def _news_timestamp_seconds(value: Any) -> float | None:
    timestamp = _safe_number(value)
    if timestamp is None or timestamp <= 0:
        return None
    if timestamp > 10_000_000_000:
        timestamp /= 1000.0
    return timestamp


def _fantasy_positions(row: Mapping[str, Any]) -> set[str]:
    value = row.get("fantasy_positions")
    if isinstance(value, (list, tuple, set)):
        positions = {_safe_text(item).upper() for item in value}
    else:
        text = _safe_text(value)
        for separator in ("|", ",", ";"):
            text = text.replace(separator, " ")
        text = text.strip("[](){}").replace('"', "").replace("'", "")
        positions = {part.upper() for part in text.split() if part}
    position = _safe_text(row.get("position")).upper()
    if position:
        positions.add(position)
    return positions & FANTASY_POSITIONS


def _trust_validation_fingerprint(
    row: Mapping[str, Any] | pd.Series,
    *,
    now: datetime,
) -> str:
    payload = {
        key: row.get(key)
        for key in TRUST_PLAYER_INPUT_COLUMNS
        if key in row
    }
    return canonical_object_key(
        "player-validation",
        {
            "player": payload,
            "eligibility_contract": PLAYER_ELIGIBILITY_CONTRACT_VERSION,
            "validation_date": now.astimezone(timezone.utc).date().isoformat(),
        },
    )


def player_eligibility(
    row: Mapping[str, Any] | pd.Series,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return current fantasy-pool eligibility from status plus corroborating current signals."""
    now = now or datetime.now(timezone.utc)
    status = _safe_text(row.get("status")).casefold()
    active = _optional_bool(row.get("active"))
    sport = _safe_text(row.get("sport")).casefold()
    positions = _fantasy_positions(row)

    if sport and sport != "nfl":
        return {"eligible": False, "reason": "non_nfl_record", "current_signal": False}
    if not positions:
        return {"eligible": False, "reason": "invalid_fantasy_position", "current_signal": False}
    # Sleeper sets `active: false` on plenty of genuinely-current IR/PUP/NFI
    # players (it tracks active-53-man-roster presence, not fantasy
    # relevance) — e.g. a season-ending-injury star is still clearly a
    # current dynasty asset. Short-circuiting here on `active` alone used to
    # drop every such player from the valued pool outright (root cause of
    # the IR-section-shows-no-value bug), even though `status` explicitly
    # says this is a reserve designation rather than a real inactive/retired
    # one. Fall through to the normal status + current-signal corroboration
    # below instead of auto-disqualifying.
    if active is False and status not in RESERVE_STATUS_TERMS:
        return {"eligible": False, "reason": "explicitly_inactive", "current_signal": False}
    if any(term in status for term in INELIGIBLE_STATUS_TERMS):
        return {"eligible": False, "reason": "retired_or_inactive_status", "current_signal": False}

    years_exp = _safe_number(row.get("years_exp"))
    rookie = active is True and years_exp is not None and years_exp <= 1

    news_timestamp = _news_timestamp_seconds(row.get("news_updated"))
    recent_news = bool(
        news_timestamp
        and (now.timestamp() - news_timestamp) <= NEWS_FRESHNESS_DAYS * 24 * 60 * 60
    )
    depth_order = _safe_number(row.get("depth_chart_order"), 0) or 0
    depth_position = _safe_text(row.get("depth_chart_position"))
    current_depth = bool(depth_position or depth_order > 0)

    stats_season = _safe_number(row.get("stats_season"))
    current_stats = bool(stats_season and stats_season >= now.year - 1)
    fantasycalc_value = _safe_number(row.get("fantasycalc_value"), 0) or 0
    current_market = fantasycalc_value > 0
    team = _safe_text(row.get("team")).strip().upper()
    no_team = not team or team in FREE_AGENT_TEAM_MARKERS
    age = _safe_number(row.get("age"))
    veteran_profile = (
        (years_exp is not None and years_exp >= VETERAN_UNSIGNED_MIN_EXPERIENCE)
        or (age is not None and age >= VETERAN_UNSIGNED_MIN_AGE)
    )
    news_only_corroboration = recent_news and not (
        current_depth or current_stats or current_market or rookie
    )
    # An unsigned veteran's current, structured news is valid corroboration. The
    # older implementation discarded *all* news-only evidence for this class,
    # which made a canonical active player disappear solely because ``team`` and
    # an optional market row were absent. Retain genuinely current evidence while
    # continuing to fail closed for old provider records that still say Active.
    unsigned_news_is_stale = bool(
        news_timestamp
        and (now.timestamp() - news_timestamp)
        > UNSIGNED_VETERAN_NEWS_FRESHNESS_DAYS * 24 * 60 * 60
    )
    if (
        veteran_profile
        and no_team
        and not current_depth
        and news_only_corroboration
        and unsigned_news_is_stale
    ):
        recent_news = False

    injury_status = _safe_text(row.get("injury_status")).casefold()
    injured_or_reserve = injury_status not in {"", "healthy", "active"} or status in {
        "injured reserve",
        "ir",
        "pup",
        "nfi",
        "out",
        "questionable",
        "doubtful",
        "practice squad",
    }
    assigned_nfl_team = bool(team) and not no_team
    stale_listed_veteran = (
        veteran_profile
        and assigned_nfl_team
        and not current_depth
        and not current_stats
        and not recent_news
        and not rookie
        and not injured_or_reserve
        and status in {"", "active"}
    )
    if stale_listed_veteran:
        # Last-known NFL club on a fully inactive veteran is not a current-asset
        # signal. Keep only when both a live market print and fresh news exist.
        current_market = bool(current_market and recent_news)
        recent_news = bool(recent_news and current_market)

    current_signal = bool(recent_news or current_depth or current_stats or current_market or rookie)

    status_is_current = status in CURRENT_STATUS_TERMS
    if active is True and current_signal:
        reason = "current_rookie" if rookie else "corroborated_current_player"
        return {"eligible": True, "reason": reason, "current_signal": True}
    if status_is_current and current_signal:
        return {"eligible": True, "reason": "corroborated_current_status", "current_signal": True}

    return {
        "eligible": False,
        "reason": "missing_current_player_corroboration",
        "current_signal": current_signal,
    }


def _annotate_player_eligibility_full(
    players: pd.DataFrame,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Reference path: every row validated from scratch, no memo.

    This is the pre-memo implementation, unchanged. ``annotate_player_eligibility``
    must stay byte-identical to it (tests/test_player_eligibility_memo_parity.py).
    It also handles empty frames and frames with duplicate column labels.
    """
    if players is None:
        return pd.DataFrame()
    annotated = players.copy()
    resolved_now = now or datetime.now(timezone.utc)
    if annotated.empty:
        annotated["is_current_fantasy_eligible"] = pd.Series(dtype="bool")
        annotated["player_eligibility_reason"] = pd.Series(dtype="object")
        annotated["trust_enforcement"] = pd.Series(dtype="object")
        annotated["trust_evidence_confidence"] = pd.Series(dtype="object")
        annotated["trust_block_reason"] = pd.Series(dtype="object")
        annotated["trust_validation_fingerprint"] = pd.Series(dtype="object")
        return annotated
    # Preserve iterrows() scalar/null semantics and the enforcement-time to_dict()
    # boundary while constructing each per-player Series only once.
    rows = [row for _, row in annotated.iterrows()]
    fingerprints = [
        _trust_validation_fingerprint(row, now=resolved_now)
        for row in rows
    ]
    if TRUST_ANNOTATION_COLUMNS.issubset(annotated.columns) and all(
        str(stored or "") == current
        for stored, current in zip(
            annotated["trust_validation_fingerprint"],
            fingerprints,
        )
    ):
        return annotated
    evaluations = [
        player_eligibility(row, now=resolved_now)
        for row in rows
    ]
    player_ids = annotated.get(
        "player_id",
        pd.Series("", index=annotated.index, dtype="object"),
    ).fillna("").astype(str).str.strip()
    duplicate_ids = frozenset(
        player_id
        for player_id, count in player_ids.value_counts().items()
        if player_id and int(count) > 1
    )
    canonical_ids = frozenset(player_id for player_id in player_ids if player_id)
    enforcement = [
        enforce_player_record(
            row,
            eligible=bool(evaluation["eligible"]),
            eligibility_reason=str(evaluation["reason"]),
            duplicate_ids=duplicate_ids,
            canonical_player_ids=canonical_ids,
        )
        for row, evaluation in zip(rows, evaluations)
    ]
    annotated["is_current_fantasy_eligible"] = [
        bool(evaluation["eligible"])
        and result.level is not EnforcementLevel.BLOCKED
        for evaluation, result in zip(evaluations, enforcement)
    ]
    annotated["player_eligibility_reason"] = [
        str(evaluation["reason"]) for evaluation in evaluations
    ]
    annotated["trust_enforcement"] = [result.level.value for result in enforcement]
    annotated["trust_evidence_confidence"] = [
        result.evidence.confidence.value for result in enforcement
    ]
    annotated["trust_block_reason"] = [
        result.reasons[0] if result.level is EnforcementLevel.BLOCKED and result.reasons else ""
        for result in enforcement
    ]
    annotated["trust_validation_fingerprint"] = fingerprints
    return annotated


def _player_id_sets(annotated: pd.DataFrame) -> tuple[frozenset[str], frozenset[str]]:
    player_ids = annotated.get(
        "player_id",
        pd.Series("", index=annotated.index, dtype="object"),
    ).fillna("").astype(str).str.strip()
    duplicate_ids = frozenset(
        player_id
        for player_id, count in player_ids.value_counts().items()
        if player_id and int(count) > 1
    )
    canonical_ids = frozenset(player_id for player_id in player_ids if player_id)
    return duplicate_ids, canonical_ids


def _write_annotation_columns(
    annotated: pd.DataFrame,
    results: list[tuple[bool, str, str, str, str, str]],
) -> pd.DataFrame:
    annotated["is_current_fantasy_eligible"] = [result[0] for result in results]
    annotated["player_eligibility_reason"] = [result[1] for result in results]
    annotated["trust_enforcement"] = [result[2] for result in results]
    annotated["trust_evidence_confidence"] = [result[3] for result in results]
    annotated["trust_block_reason"] = [result[4] for result in results]
    annotated["trust_validation_fingerprint"] = [result[5] for result in results]
    return annotated


def _annotate_one_row(
    row: pd.Series,
    *,
    fingerprint: str,
    now: datetime,
    duplicate_ids: frozenset[str],
    canonical_ids: frozenset[str],
) -> tuple[bool, str, str, str, str, str]:
    evaluation = player_eligibility(row, now=now)
    result = enforce_player_record(
        row,
        eligible=bool(evaluation["eligible"]),
        eligibility_reason=str(evaluation["reason"]),
        duplicate_ids=duplicate_ids,
        canonical_player_ids=canonical_ids,
    )
    blocked = result.level is EnforcementLevel.BLOCKED
    return (
        bool(evaluation["eligible"]) and not blocked,
        str(evaluation["reason"]),
        result.level.value,
        result.evidence.confidence.value,
        result.reasons[0] if blocked and result.reasons else "",
        fingerprint,
    )


# --- Incremental annotation -------------------------------------------------
#
# Every Sleeper dump refresh (5-minute TTL) changes the public-player source
# fingerprint, and the rebuild re-validated every player from scratch, twice
# (iterrows + to_dict + a JSON/sha256 of every full row), when typically ~9
# players' news timestamps had actually changed. Each player's result is a
# pure function of
#   * the row's values in _ANNOTATION_INPUT_COLUMNS: every field that
#     player_eligibility, enforce_player_record (validate_player) and
#     _trust_validation_fingerprint read,
#   * whether its player_id is duplicated / canonical in this frame,
#   * the clock, only through: now.year, now's UTC date (fingerprint),
#     today's UTC date (validate_player's freshness bucket), and the two
#     news-age threshold comparisons, evaluated per row in the key,
#   * the code and constants of this module, trust_enforcement and
#     trust_engine, the pandas/numpy/Python versions, and the process
#     timezone (naive datetimes in trust_engine._stable_payload).
# The memo key covers all of it, so a hit returns exactly what a full
# recompute would (tests/test_player_eligibility_memo_parity.py). Values the
# key can't encode faithfully are just recomputed.
#
# Two tiers: a per-process LRU (the second annotate in the same rebuild is
# then all hits) and Redis, so a cold process (a freshly started worker, or
# the players.db rebuild subprocess that runs every refresh) reuses what any
# other process already computed. Redis is skipped whenever any of the code
# above is monkeypatched in-process, and fails open.

_ANNOTATION_INPUT_COLUMNS = tuple(
    dict.fromkeys((*TRUST_PLAYER_INPUT_COLUMNS, "injury_status"))
)
_ANNOTATION_MEMO_MAX_ENTRIES = 16384
_ANNOTATION_MEMO: OrderedDict[bytes, tuple[bool, str, str, str, str, str]] = OrderedDict()
_ANNOTATION_MEMO_GUARD = threading.Lock()
_ANNOTATION_MEMO_STATS = {"hits": 0, "redis_hits": 0, "misses": 0, "uncacheable": 0}
_REDIS_MEMO_PREFIX = b"player_annotation_memo:v1:"
# The key embeds today's date, so entries are dead after a day anyway.
_REDIS_MEMO_TTL_SECONDS = 26 * 60 * 60
_REDIS_MEMO_RETRY_AFTER_SECONDS = 30.0
_redis_memo_down_until = 0.0


class _UncacheableValue(Exception):
    pass


def _memo_token(value: Any) -> Any:
    """Hashable, type-tagged encoding that distinguishes every value the
    validators can tell apart (1 vs 1.0 vs True vs "1", NaN, tz-aware vs
    naive, container order). Raises for anything it can't encode exactly."""

    value_type = type(value)
    if value is None:
        return "N"
    if value_type is str:
        return ("s", value)
    if value_type is bool:
        return ("b", value)
    if value_type is int:
        return ("i", value)
    if value_type is float:
        return ("f", repr(value))
    if value is pd.NA:
        return ("NA",)
    if value is pd.NaT:
        return ("NaT",)
    type_name = f"{value_type.__module__}.{value_type.__qualname__}"
    if isinstance(value, np.generic):
        return ("np", type_name, repr(value))
    if isinstance(value, datetime):
        return ("dt", type_name, value.isoformat(), repr(value.tzinfo))
    if isinstance(value, (list, tuple, set, frozenset)):
        return ("seq", type_name, tuple(_memo_token(item) for item in value))
    if isinstance(value, dict):
        return (
            "map",
            type_name,
            tuple((_memo_token(key), _memo_token(item)) for key, item in value.items()),
        )
    raise _UncacheableValue(type_name)


def _behavior_ids() -> tuple[int, ...]:
    return tuple(
        id(function)
        for function in (
            player_eligibility,
            enforce_player_record,
            _trust_validation_fingerprint,
            _fantasy_positions,
            _news_timestamp_seconds,
            _safe_text,
            _optional_bool,
            _safe_number,
            _trust_enforcement.validate_player,
            _trust_enforcement._evidence,
            _trust_engine._validate,
            _trust_engine._cached_validation,
            _trust_engine._validate_player,
            _trust_engine._freshness,
            _trust_engine._signals,
            _trust_engine._conflicts,
            _trust_engine._result,
            _trust_engine._stable_payload,
            _trust_engine._now_bucket,
            _trust_engine.canonical_object_key,
        )
    )


def _constants_repr() -> str:
    return repr(
        (
            sorted(FANTASY_POSITIONS),
            sorted(INELIGIBLE_STATUS_TERMS),
            sorted(CURRENT_STATUS_TERMS),
            sorted(RESERVE_STATUS_TERMS),
            sorted(FREE_AGENT_TEAM_MARKERS),
            NEWS_FRESHNESS_DAYS,
            UNSIGNED_VETERAN_NEWS_FRESHNESS_DAYS,
            VETERAN_UNSIGNED_MIN_EXPERIENCE,
            VETERAN_UNSIGNED_MIN_AGE,
            PLAYER_ELIGIBILITY_CONTRACT_VERSION,
            TRUST_PLAYER_INPUT_COLUMNS,
        )
    )


def _code_version_digest() -> str:
    digest = hashlib.sha256()
    for module_file in (__file__, _trust_enforcement.__file__, _trust_engine.__file__):
        try:
            with open(module_file, "rb") as handle:
                digest.update(handle.read())
        except OSError:
            digest.update(f"unreadable:{module_file}".encode())
    digest.update(f"{sys.version}|{pd.__version__}|{np.__version__}".encode())
    return digest.hexdigest()


def _annotation_context(columns: pd.Index, *, now: datetime) -> tuple[str, bool]:
    """(key context, shareable across processes)."""

    behavior_ids = _behavior_ids()
    constants = _constants_repr()
    shareable = behavior_ids == _IMPORT_BEHAVIOR_IDS and constants == _IMPORT_CONSTANTS_REPR
    context = (
        tuple(column for column in _ANNOTATION_INPUT_COLUMNS if column in columns),
        now.year,
        now.astimezone(timezone.utc).date().isoformat(),
        _trust_engine._now_bucket(None),
        _CODE_VERSION_DIGEST if shareable else ("patched", behavior_ids),
        constants,
        time.timezone,
        time.altzone,
        time.daylight,
        time.tzname,
    )
    return repr(context), shareable


def _row_memo_key(
    values: Any,
    *,
    positions: tuple[int, ...],
    player_id_position: int | None,
    news_position: int | None,
    context_repr: str,
    now_seconds: float,
    duplicate_ids: frozenset[str],
    canonical_ids: frozenset[str],
) -> bytes | None:
    """Memo key for one row, or None (row is recomputed, not memoized) when
    any value can't be encoded exactly or the key itself can't be built."""

    try:
        tokens = tuple(_memo_token(values[position]) for position in positions)
        raw_player_id = values[player_id_position] if player_id_position is not None else None
        # enforce_player_record's own normalization of the id (str(v or "").strip()).
        player_id = str(raw_player_id or "").strip()
        news_seconds = _news_timestamp_seconds(
            values[news_position] if news_position is not None else None
        )
        news_age = (now_seconds - news_seconds) if news_seconds else None
        payload = repr(
            (
                context_repr,
                tokens,
                player_id in duplicate_ids,
                player_id in canonical_ids,
                bool(news_seconds and news_age <= NEWS_FRESHNESS_DAYS * 24 * 60 * 60),
                bool(
                    news_seconds
                    and news_age > UNSIGNED_VETERAN_NEWS_FRESHNESS_DAYS * 24 * 60 * 60
                ),
            )
        )
    except Exception:
        return None
    return hashlib.blake2b(
        payload.encode("utf-8", "surrogatepass"),
        digest_size=16,
    ).digest()


def _valid_memo_result(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 6
        and type(value[0]) is bool
        and all(type(item) is str for item in value[1:])
    )


def _redis_memo_client() -> Any:
    if time.monotonic() < _redis_memo_down_until:
        return None
    try:
        from modules import redis_cache

        return redis_cache.get_redis_client()
    except Exception:
        return None


def _redis_memo_failed() -> None:
    global _redis_memo_down_until
    _redis_memo_down_until = time.monotonic() + _REDIS_MEMO_RETRY_AFTER_SECONDS


def _redis_memo_get(keys: list[bytes]) -> dict[bytes, tuple[bool, str, str, str, str, str]]:
    client = _redis_memo_client() if keys else None
    if client is None:
        return {}
    try:
        raw = client.mget([_REDIS_MEMO_PREFIX + key.hex().encode() for key in keys])
    except Exception:
        _redis_memo_failed()
        return {}
    found: dict[bytes, tuple[bool, str, str, str, str, str]] = {}
    for key, payload in zip(keys, raw or ()):
        if payload is None:
            continue
        try:
            value = json.loads(payload)
        except (TypeError, ValueError):
            continue
        if _valid_memo_result(value):
            found[key] = tuple(value)  # type: ignore[assignment]
    return found


def _redis_memo_set(entries: list[tuple[bytes, tuple[bool, str, str, str, str, str]]]) -> None:
    client = _redis_memo_client() if entries else None
    if client is None:
        return
    try:
        pipe = client.pipeline(transaction=False)
        for key, result in entries:
            pipe.set(
                _REDIS_MEMO_PREFIX + key.hex().encode(),
                json.dumps(list(result), separators=(",", ":")),
                ex=_REDIS_MEMO_TTL_SECONDS,
            )
        pipe.execute()
    except Exception:
        _redis_memo_failed()


def clear_player_annotation_memo() -> None:
    """Drop this process's tier (Redis entries expire on their own)."""

    global _redis_memo_down_until
    with _ANNOTATION_MEMO_GUARD:
        _ANNOTATION_MEMO.clear()
        for name in _ANNOTATION_MEMO_STATS:
            _ANNOTATION_MEMO_STATS[name] = 0
    _redis_memo_down_until = 0.0


def player_annotation_memo_stats() -> dict[str, int]:
    with _ANNOTATION_MEMO_GUARD:
        return {**_ANNOTATION_MEMO_STATS, "entries": len(_ANNOTATION_MEMO)}


def annotate_player_eligibility(
    players: pd.DataFrame,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    if players is None:
        return pd.DataFrame()
    if not players.columns.is_unique:
        return _annotate_player_eligibility_full(players, now=now)
    annotated = players.copy()
    resolved_now = now or datetime.now(timezone.utc)
    if annotated.empty:
        return _annotate_player_eligibility_full(players, now=resolved_now)

    columns = annotated.columns
    # Exactly the per-row objects iterrows() yields (it iterates self.values).
    values = annotated.values
    index = annotated.index
    positions = tuple(
        columns.get_loc(column) for column in _ANNOTATION_INPUT_COLUMNS if column in columns
    )
    player_id_position = columns.get_loc("player_id") if "player_id" in columns else None
    news_position = columns.get_loc("news_updated") if "news_updated" in columns else None
    duplicate_ids, canonical_ids = _player_id_sets(annotated)
    context_repr, shareable = _annotation_context(columns, now=resolved_now)
    now_seconds = resolved_now.timestamp()

    row_count = len(values)
    keys = [
        _row_memo_key(
            values[position],
            positions=positions,
            player_id_position=player_id_position,
            news_position=news_position,
            context_repr=context_repr,
            now_seconds=now_seconds,
            duplicate_ids=duplicate_ids,
            canonical_ids=canonical_ids,
        )
        for position in range(row_count)
    ]
    results: list[tuple[bool, str, str, str, str, str] | None] = [None] * row_count
    with _ANNOTATION_MEMO_GUARD:
        for position, key in enumerate(keys):
            if key is None:
                continue
            cached = _ANNOTATION_MEMO.get(key)
            if cached is not None:
                _ANNOTATION_MEMO.move_to_end(key)
                results[position] = cached
    redis_hits = 0
    if shareable:
        wanted = list(
            dict.fromkeys(
                key for key, result in zip(keys, results) if key is not None and result is None
            )
        )
        shared = _redis_memo_get(wanted)
        if shared:
            for position, key in enumerate(keys):
                if results[position] is None and key in shared:
                    results[position] = shared[key]
                    redis_hits += 1
            with _ANNOTATION_MEMO_GUARD:
                for key, result in shared.items():
                    _ANNOTATION_MEMO[key] = result

    row_class = annotated._constructor_sliced
    miss_rows: dict[int, pd.Series] = {}
    fingerprints: list[str] = []
    for position in range(row_count):
        cached = results[position]
        if cached is not None:
            fingerprints.append(cached[5])
            continue
        row = row_class(values[position], index=columns, name=index[position]).__finalize__(
            annotated
        )
        miss_rows[position] = row
        fingerprints.append(_trust_validation_fingerprint(row, now=resolved_now))

    if TRUST_ANNOTATION_COLUMNS.issubset(columns) and all(
        str(stored or "") == current
        for stored, current in zip(
            annotated["trust_validation_fingerprint"],
            fingerprints,
        )
    ):
        return annotated

    fresh: list[tuple[bytes, tuple[bool, str, str, str, str, str]]] = []
    for position, row in miss_rows.items():
        result = _annotate_one_row(
            row,
            fingerprint=fingerprints[position],
            now=resolved_now,
            duplicate_ids=duplicate_ids,
            canonical_ids=canonical_ids,
        )
        results[position] = result
        if keys[position] is not None:
            fresh.append((keys[position], result))
    uncacheable = sum(1 for key in keys if key is None)
    with _ANNOTATION_MEMO_GUARD:
        for key, result in fresh:
            _ANNOTATION_MEMO[key] = result
            _ANNOTATION_MEMO.move_to_end(key)
        while len(_ANNOTATION_MEMO) > _ANNOTATION_MEMO_MAX_ENTRIES:
            _ANNOTATION_MEMO.popitem(last=False)
        _ANNOTATION_MEMO_STATS["uncacheable"] += uncacheable
        _ANNOTATION_MEMO_STATS["misses"] += len(miss_rows) - uncacheable
        _ANNOTATION_MEMO_STATS["redis_hits"] += redis_hits
        _ANNOTATION_MEMO_STATS["hits"] += row_count - len(miss_rows) - redis_hits
    if shareable:
        _redis_memo_set(fresh)
    return _write_annotation_columns(annotated, results)  # type: ignore[arg-type]


_CODE_VERSION_DIGEST = _code_version_digest()
_IMPORT_BEHAVIOR_IDS = _behavior_ids()
_IMPORT_CONSTANTS_REPR = _constants_repr()


def eligibility_diagnostics(players: pd.DataFrame) -> dict[str, int]:
    if players is None or players.empty:
        return {
            "input_count": 0,
            "eligible_count": 0,
            "removed_retired_or_inactive": 0,
            "retained_current_free_agents": 0,
            "players_validated": 0,
            "players_passed": 0,
            "players_degraded": 0,
            "players_blocked": 0,
        }
    annotated = (
        players
        if "is_current_fantasy_eligible" in players.columns
        and "player_eligibility_reason" in players.columns
        and "trust_enforcement" in players.columns
        else annotate_player_eligibility(players)
    )
    eligible = annotated["is_current_fantasy_eligible"].fillna(False).astype(bool)
    team = annotated.get(
        "team",
        pd.Series("", index=annotated.index, dtype="object"),
    ).fillna("").astype(str).str.strip().str.upper()
    reasons = annotated["player_eligibility_reason"].fillna("").astype(str)
    return {
        "input_count": int(len(annotated)),
        "eligible_count": int(eligible.sum()),
        "removed_retired_or_inactive": int(
            (
                ~eligible
                & reasons.isin(
                    {
                        "explicitly_inactive",
                        "retired_or_inactive_status",
                        "missing_current_player_corroboration",
                    }
                )
            ).sum()
        ),
        "retained_current_free_agents": int(
            (eligible & team.isin(FREE_AGENT_TEAM_MARKERS)).sum()
        ),
        "players_validated": int(len(annotated)),
        "players_passed": int(
            (annotated.get("trust_enforcement", "") == EnforcementLevel.PASS.value).sum()
        ),
        "players_degraded": int(
            (annotated.get("trust_enforcement", "") == EnforcementLevel.DEGRADED.value).sum()
        ),
        "players_blocked": int(
            (annotated.get("trust_enforcement", "") == EnforcementLevel.BLOCKED.value).sum()
        ),
    }


def is_current_fantasy_asset(
    row: Mapping[str, Any] | pd.Series,
    *,
    now: datetime | None = None,
) -> bool:
    """Canonical current-asset predicate — one owner for every consumer surface."""

    return bool(player_eligibility(row, now=now)["eligible"])


def filter_current_fantasy_players(
    players: pd.DataFrame,
    *,
    surface: str = "",
    now: datetime | None = None,
    league: dict | None = None,
) -> pd.DataFrame:
    """Filter before ranking while preserving the original order of eligible rows.

    `league` is optional and, when passed, additionally drops DEF/D-ST and
    kicker rows for a league whose own `roster_positions` don't include
    that slot at all — those players were showing up in rankings/search/
    waivers for leagues that can never actually roster them (niche-scenario
    audit, 2026-10-17: kicker-gating was missing even though DEF already
    had this exact guard — same bug class, just never extended to K).
    Every existing caller that doesn't pass `league` keeps its exact
    current behavior; this is opt-in per call site, not a blanket behavior
    change.
    """
    if players is None:
        players = pd.DataFrame()
    # Prepared / snapshot frames already carry the canonical flag. Re-running
    # annotate_player_eligibility() would iterrows+fingerprint the pool on every
    # route (Waivers, Trade search, explorer) and looks like a navigation hang.
    if (
        not players.empty
        and TRUST_ANNOTATION_COLUMNS.issubset(players.columns)
    ):
        annotated = players
    else:
        annotated = annotate_player_eligibility(players, now=now)
    diagnostics = eligibility_diagnostics(annotated)
    try:
        from modules import performance

        if performance.debug_enabled():
            payload = {
                "surface": str(surface or "decision_pool")[:64],
                **diagnostics,
            }
            print(
                "DYNASTYGM_PLAYER_ELIGIBILITY " + json.dumps(payload, sort_keys=True),
                flush=True,
            )
            performance.record_trust_diagnostics(diagnostics)
    except Exception:
        pass
    if annotated.empty:
        return annotated
    eligible = annotated[annotated["is_current_fantasy_eligible"].fillna(False).astype(bool)].copy()
    if league is not None and "position" in eligible.columns:
        roster_positions = league.get("roster_positions") or []
        if "DEF" not in roster_positions:
            eligible = eligible[eligible["position"] != "DEF"]
        if "K" not in roster_positions:
            eligible = eligible[eligible["position"] != "K"]
    return eligible
