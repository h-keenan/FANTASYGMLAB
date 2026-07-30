"""Shared trust, evidence, and validation primitives for DynastyGM.

This module is deliberately independent from recommendation generation.  It
describes the quality of inputs and computed outputs without changing any
fantasy score, rank, package, or recommendation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence


class DataTier(IntEnum):
    CANONICAL = 1
    VERIFIED = 2
    EVALUATED = 3


class Freshness(StrEnum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class FieldTrust:
    tier: DataTier
    source: str


@dataclass(frozen=True)
class Evidence:
    available: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    freshness: Freshness = Freshness.UNKNOWN
    confidence_inputs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()
    observed_at: str = ""

    @property
    def confidence(self) -> ConfidenceLevel:
        if self.freshness is Freshness.STALE or self.missing or self.uncertainty:
            return ConfidenceLevel.LOW
        if self.freshness in {Freshness.AGING, Freshness.UNKNOWN} or self.assumptions:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.HIGH


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    warnings: tuple[str, ...]
    confidence: ConfidenceLevel
    stale_indicators: tuple[str, ...]
    evidence: Evidence


@dataclass(frozen=True)
class RecommendationConfidence:
    model_confidence: ConfidenceLevel
    evidence_confidence: ConfidenceLevel
    effective_confidence: ConfidenceLevel
    reasons: tuple[str, ...] = ()


FIELD_TRUST: dict[str, FieldTrust] = {
    # Tier 1: exactly one canonical source.
    "league_settings": FieldTrust(DataTier.CANONICAL, "sleeper"),
    "league_rosters": FieldTrust(DataTier.CANONICAL, "sleeper"),
    "player_id": FieldTrust(DataTier.CANONICAL, "sleeper"),
    "draft_picks": FieldTrust(DataTier.CANONICAL, "sleeper"),
    "current_ownership": FieldTrust(DataTier.CANONICAL, "sleeper"),
    "matchups": FieldTrust(DataTier.CANONICAL, "sleeper"),
    "transactions": FieldTrust(DataTier.CANONICAL, "sleeper"),
    # Tier 2: current signals may corroborate these fields.
    "injury": FieldTrust(DataTier.VERIFIED, "corroborated_current_signals"),
    "player_status": FieldTrust(DataTier.VERIFIED, "corroborated_current_signals"),
    "depth_chart": FieldTrust(DataTier.VERIFIED, "corroborated_current_signals"),
    "team": FieldTrust(DataTier.VERIFIED, "corroborated_current_signals"),
    "age": FieldTrust(DataTier.VERIFIED, "corroborated_current_signals"),
    "bye_week": FieldTrust(DataTier.VERIFIED, "corroborated_current_signals"),
    # Tier 3: DynastyGM evaluations, never external facts.
    "dynasty_score": FieldTrust(DataTier.EVALUATED, "dynastygm"),
    "startup_score": FieldTrust(DataTier.EVALUATED, "dynastygm"),
    "contender_score": FieldTrust(DataTier.EVALUATED, "dynastygm"),
    "rebuild_score": FieldTrust(DataTier.EVALUATED, "dynastygm"),
    "trade_value": FieldTrust(DataTier.EVALUATED, "dynastygm"),
    "roster_fit": FieldTrust(DataTier.EVALUATED, "dynastygm"),
    "confidence": FieldTrust(DataTier.EVALUATED, "dynastygm"),
    "opportunity": FieldTrust(DataTier.EVALUATED, "dynastygm"),
    "tier": FieldTrust(DataTier.EVALUATED, "dynastygm"),
    "archetype": FieldTrust(DataTier.EVALUATED, "dynastygm"),
}


def field_trust(field_name: str) -> FieldTrust:
    """Return the single declared trust policy for a known field."""

    try:
        return FIELD_TRUST[str(field_name).strip().casefold()]
    except KeyError as exc:
        raise ValueError(f"Unclassified trust field: {field_name!r}") from exc


def recommendation_confidence(
    model_confidence: ConfidenceLevel | str,
    evidence: Evidence | ConfidenceLevel | str,
) -> RecommendationConfidence:
    """Cap model confidence at the quality of its evidence."""

    model = ConfidenceLevel(str(model_confidence).casefold())
    evidence_level = (
        evidence.confidence
        if isinstance(evidence, Evidence)
        else ConfidenceLevel(str(evidence).casefold())
    )
    order = {
        ConfidenceLevel.LOW: 0,
        ConfidenceLevel.MEDIUM: 1,
        ConfidenceLevel.HIGH: 2,
    }
    effective = min((model, evidence_level), key=order.__getitem__)
    reasons = ()
    if effective is not model:
        reasons = ("Model confidence capped by evidence quality.",)
    return RecommendationConfidence(model, evidence_level, effective, reasons)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000
        try:
            parsed = datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        try:
            parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _freshness(updated_at: Any, *, now: datetime) -> tuple[Freshness, tuple[str, ...]]:
    updated = _parse_time(updated_at)
    if updated is None:
        return Freshness.UNKNOWN, ("No reliable update timestamp.",)
    age_days = max(0, (now - updated).days)
    if age_days > 730:
        return Freshness.STALE, (f"Metadata is {age_days} days old.",)
    if age_days > 180:
        return Freshness.AGING, (f"Metadata is {age_days} days old.",)
    return Freshness.CURRENT, ()


def _signals(record: Mapping[str, Any]) -> list[str]:
    names = (
        "team",
        "depth_chart_position",
        "depth_chart_order",
        "latest_stats_season",
        "fantasycalc_value",
        "news_updated_at",
    )
    return [name for name in names if record.get(name) not in (None, "", 0, False)]


def _conflicts(record: Mapping[str, Any]) -> tuple[str, ...]:
    conflicts: list[str] = []
    supplied = record.get("verified_signals")
    if isinstance(supplied, Mapping):
        for name, values in supplied.items():
            if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                normalized = {_text(value).casefold() for value in values if _text(value)}
                if len(normalized) > 1:
                    conflicts.append(f"Conflicting {name} metadata.")
    status = _text(record.get("status")).casefold()
    active = record.get("active")
    if active is True and status in {"retired", "inactive", "deceased"}:
        conflicts.append("Player is marked active with an inactive status.")
    if active is False and status in {"active", "playing"}:
        conflicts.append("Player is marked inactive with an active status.")
    return _unique(conflicts)


def _result(
    *,
    warnings: Iterable[str],
    stale: Iterable[str] = (),
    available: Iterable[str] = (),
    missing: Iterable[str] = (),
    inputs: Iterable[str] = (),
    assumptions: Iterable[str] = (),
    uncertainty: Iterable[str] = (),
    freshness: Freshness = Freshness.UNKNOWN,
    observed_at: str = "",
) -> ValidationResult:
    warning_items = _unique(warnings)
    stale_items = _unique(stale)
    evidence = Evidence(
        available=_unique(available),
        missing=_unique(missing),
        freshness=freshness,
        confidence_inputs=_unique(inputs),
        assumptions=_unique(assumptions),
        uncertainty=_unique(uncertainty),
        observed_at=observed_at,
    )
    return ValidationResult(
        valid=not warning_items and not stale_items and not evidence.missing,
        warnings=warning_items,
        confidence=evidence.confidence,
        stale_indicators=stale_items,
        evidence=evidence,
    )


def _stable_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _stable_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted((_stable_payload(item) for item in value), key=str)
    if isinstance(value, (list, tuple)):
        return [_stable_payload(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def canonical_object_key(kind: str, record: Mapping[str, Any]) -> str:
    """Create a sanitized, content-addressed key without leaking raw identifiers."""

    payload = json.dumps(
        _stable_payload(record),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{_text(kind).casefold()}:{digest}"


def _now_bucket(now: datetime | None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).date().isoformat()


@lru_cache(maxsize=8192)
def _cached_validation(
    kind: str,
    object_key: str,
    payload: str,
    now_bucket: str,
) -> ValidationResult:
    del object_key
    record = json.loads(payload)
    now = datetime.fromisoformat(now_bucket).replace(tzinfo=UTC)
    validators = {
        "player": _validate_player,
        "league": _validate_league,
        "roster": _validate_roster,
        "pick": _validate_pick,
        "trade": _validate_trade,
    }
    try:
        validator = validators[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported trust object: {kind!r}") from exc
    return validator(record, now=now)


def _validate(kind: str, record: Mapping[str, Any], *, now: datetime | None) -> ValidationResult:
    stable = _stable_payload(record)
    payload = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return _cached_validation(
        kind,
        canonical_object_key(kind, record),
        payload,
        _now_bucket(now),
    )


def validate_player(player: Mapping[str, Any], *, now: datetime | None = None) -> ValidationResult:
    return _validate("player", player, now=now)


def _validate_player(player: Mapping[str, Any], *, now: datetime) -> ValidationResult:
    warnings: list[str] = list(_conflicts(player))
    missing: list[str] = []
    player_id = _text(player.get("player_id"))
    if not player_id:
        missing.append("player_id")
    freshness, age_notes = _freshness(
        player.get("metadata_updated_at")
        or player.get("news_updated_at")
        or player.get("news_updated")
        or player.get("updated_at"),
        now=now,
    )
    status = _text(player.get("status")).casefold()
    active = player.get("active")
    stale = list(age_notes if freshness is Freshness.STALE else ())
    current_signals = _signals(player)
    if active is True and freshness is Freshness.STALE and not current_signals:
        stale.append("Active player has no meaningful current signal.")
    if active is True and status in {"retired", "inactive", "deceased"}:
        stale.append("Retired or inactive player is still marked active.")
    if player.get("verified_signals") and len(current_signals) < 2:
        warnings.append("Verified metadata lacks two agreeing current signals.")
    return _result(
        warnings=warnings,
        stale=stale,
        available=(("player_id",) if player_id else ()) + tuple(current_signals),
        missing=missing,
        inputs=("canonical player identity", "current player signals"),
        uncertainty=warnings,
        freshness=freshness,
        observed_at=_text(
            player.get("metadata_updated_at")
            or player.get("news_updated_at")
            or player.get("news_updated")
            or player.get("updated_at")
        ),
    )


def validate_players(
    players: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> tuple[ValidationResult, ...]:
    rows = tuple(players)
    counts: dict[str, int] = {}
    for row in rows:
        player_id = _text(row.get("player_id"))
        if player_id:
            counts[player_id] = counts.get(player_id, 0) + 1
    results = []
    for row in rows:
        result = validate_player(row, now=now)
        player_id = _text(row.get("player_id"))
        if player_id and counts.get(player_id, 0) > 1:
            result = _result(
                warnings=result.warnings + ("Duplicate canonical player ID.",),
                stale=result.stale_indicators,
                available=result.evidence.available,
                missing=result.evidence.missing,
                inputs=result.evidence.confidence_inputs,
                assumptions=result.evidence.assumptions,
                uncertainty=result.evidence.uncertainty + ("Identity is not unique.",),
                freshness=result.evidence.freshness,
                observed_at=result.evidence.observed_at,
            )
        results.append(result)
    return tuple(results)


def validate_league(league: Mapping[str, Any], *, now: datetime | None = None) -> ValidationResult:
    return _validate("league", league, now=now)


def _validate_league(league: Mapping[str, Any], *, now: datetime) -> ValidationResult:
    del now
    missing = [
        name
        for name in ("league_id", "settings", "roster_positions")
        if league.get(name) in (None, "", [], {})
    ]
    warnings: list[str] = []
    settings = league.get("settings")
    if settings not in (None, "") and not isinstance(settings, Mapping):
        warnings.append("League settings are not a mapping.")
    positions = league.get("roster_positions")
    if positions not in (None, "") and (
        not isinstance(positions, Sequence) or isinstance(positions, (str, bytes))
    ):
        warnings.append("Roster positions are not a sequence.")
    team_count = league.get("total_rosters") or league.get("num_teams")
    if team_count is not None:
        try:
            if int(team_count) <= 1:
                warnings.append("League team count is impossible.")
        except (TypeError, ValueError):
            warnings.append("League team count is invalid.")
    return _result(
        warnings=warnings,
        available=("Sleeper league settings",),
        missing=missing,
        inputs=("canonical Sleeper league object",),
        uncertainty=warnings,
        freshness=Freshness.CURRENT,
    )


def validate_roster(roster: Mapping[str, Any], *, now: datetime | None = None) -> ValidationResult:
    return _validate("roster", roster, now=now)


def _validate_roster(roster: Mapping[str, Any], *, now: datetime) -> ValidationResult:
    del now
    missing = [name for name in ("roster_id", "players") if roster.get(name) in (None, "")]
    warnings: list[str] = []
    players = roster.get("players")
    if players is not None:
        if not isinstance(players, Sequence) or isinstance(players, (str, bytes)):
            warnings.append("Roster players are not a sequence.")
        else:
            normalized = [_text(value) for value in players if _text(value)]
            if len(normalized) != len(set(normalized)):
                warnings.append("Roster contains duplicate player IDs.")
    return _result(
        warnings=warnings,
        available=("canonical roster",) if not missing else (),
        missing=missing,
        inputs=("canonical Sleeper roster object",),
        uncertainty=warnings,
        freshness=Freshness.CURRENT,
    )


def validate_pick(pick: Mapping[str, Any], *, now: datetime | None = None) -> ValidationResult:
    return _validate("pick", pick, now=now)


def _validate_pick(pick: Mapping[str, Any], *, now: datetime) -> ValidationResult:
    del now
    missing = [name for name in ("season", "round") if pick.get(name) in (None, "")]
    warnings: list[str] = []
    try:
        if pick.get("round") not in (None, "") and int(pick["round"]) <= 0:
            warnings.append("Draft-pick round is invalid.")
    except (TypeError, ValueError):
        warnings.append("Draft-pick round is invalid.")
    try:
        if pick.get("season") not in (None, "") and int(pick["season"]) < 2000:
            warnings.append("Draft-pick season is invalid.")
    except (TypeError, ValueError):
        warnings.append("Draft-pick season is invalid.")
    return _result(
        warnings=warnings,
        available=("canonical draft pick",) if not missing else (),
        missing=missing,
        inputs=("canonical Sleeper draft-pick object",),
        uncertainty=warnings,
        freshness=Freshness.CURRENT,
    )


def validate_trade(trade: Mapping[str, Any], *, now: datetime | None = None) -> ValidationResult:
    return _validate("trade", trade, now=now)


def _validate_trade(trade: Mapping[str, Any], *, now: datetime) -> ValidationResult:
    del now
    send = trade.get("send_assets")
    receive = trade.get("receive_assets")
    missing = [
        label
        for label, value in (("send_assets", send), ("receive_assets", receive))
        if not value
    ]
    warnings: list[str] = []
    if send and receive:
        send_ids = {
            _text(asset.get("player_id") or asset.get("pick_id") or asset.get("id"))
            for asset in send
            if isinstance(asset, Mapping)
        }
        receive_ids = {
            _text(asset.get("player_id") or asset.get("pick_id") or asset.get("id"))
            for asset in receive
            if isinstance(asset, Mapping)
        }
        send_ids.discard("")
        receive_ids.discard("")
        if send_ids & receive_ids:
            warnings.append("The same canonical asset appears on both trade sides.")
        if len(send_ids) != len(send):
            warnings.append("One or more outgoing assets lack a canonical ID.")
        if len(receive_ids) != len(receive):
            warnings.append("One or more incoming assets lack a canonical ID.")
    return _result(
        warnings=warnings,
        available=("trade assets",) if not missing else (),
        missing=missing,
        inputs=("canonical asset IDs", "evaluated trade output"),
        uncertainty=warnings,
        freshness=Freshness.CURRENT,
    )


def validation_cache_info():
    return _cached_validation.cache_info()


def clear_validation_cache() -> None:
    _cached_validation.cache_clear()


def evidence_dict(evidence: Evidence) -> dict[str, Any]:
    """Serializable evidence for future API/UI integration."""

    payload = asdict(evidence)
    payload["freshness"] = evidence.freshness.value
    payload["confidence"] = evidence.confidence.value
    return payload
