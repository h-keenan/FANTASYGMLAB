"""Identity, availability provenance and claim evidence for the ad API.

Pure builders (no I/O, no network, no clock reads): the providers in
``modules.external_ad_api`` load the raw rows and hand them in. Three blocks are
added, additively, to ``modules.external_ad_api`` items:

* ``identity``      canonical player ids. A null id means "not mapped"; every
                    null carries a machine-readable reason. Ids are never guessed.
* ``availability``  injury/status provenance: where a designation came from,
                    whether that source is official, and when it was observed.
* ``claims[]``      each factual or recommendation statement with its
                    ``claim_status`` (confirmed | reported | unverified), evidence,
                    method, confidence and an ``auto_publish_eligible`` flag.

Rules that cannot be bypassed (see ``finalize_claim`` and the tests):

* ``confirmed`` requires at least one evidence row that is an official NFL
  injury-report row we ingested (``source_type == "official_team_report"`` and
  ``is_official``). News, Sleeper status and our own models never confirm.
* ``auto_publish_eligible`` requires ``confirmed`` AND a source timestamp that is
  inside ``AUTO_PUBLISH_FRESH_HOURS`` AND the report week equal to the week the
  item is about AND no disagreeing source. A missing timestamp is "cannot prove
  fresh", never "fresh".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

CLAIM_STATUSES = ("confirmed", "reported", "unverified")
SOURCE_TYPES = ("official_team_report", "league_transaction", "platform_status", "news_report", "inferred")

# An official designation is only auto-publishable while the report row itself
# was stamped within this many hours of the response. NFL final game-status
# designations are issued Friday (Sunday games) and can change after, so this
# is deliberately short.
AUTO_PUBLISH_FRESH_HOURS = 48.0
FUTURE_TOLERANCE = timedelta(minutes=5)

OFFICIAL_SOURCE_NAME = "NFL official injury report (via nflverse)"
OFFICIAL_URL_TEMPLATE = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"
PLATFORM_SOURCE_NAME = "Sleeper player directory"

# Cross-platform ids we expose. field -> (sleeper dump key, DynastyProcess column or None)
ID_FIELDS: dict[str, tuple[str | None, str | None]] = {
    "gsis_id": ("gsis_id", "gsis_id"),
    "espn_id": ("espn_id", "espn_id"),
    "yahoo_id": ("yahoo_id", "yahoo_id"),
    "pfr_id": (None, "pfr_id"),
    "fantasypros_id": (None, "fantasypros_id"),
    "sportradar_id": ("sportradar_id", None),
    "rotowire_id": ("rotowire_id", None),
}
DP_COLUMNS = tuple(dp for _, dp in ID_FIELDS.values() if dp) + ("sleeper_id",)

_GSIS_RE = re.compile(r"^00-\d{7}$")
_MISSING = {"", "nan", "none", "null", "na", "n/a"}
# Designations that mean "will not play this game"; Out on the official report
# and IR/PUP/NFI/Suspended on Sleeper describe the same availability.
_UNAVAILABLE_GROUP = {"out", "ir", "pup", "nfi", "sus", "suspended", "dnr"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _clean_id(value: Any) -> str:
    text = _text(value)
    if text.lower() in _MISSING:
        return ""
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    return text


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_ts(value: Any) -> datetime | None:
    """ISO string / epoch seconds / datetime -> aware UTC datetime, else None."""

    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc) if value > 0 else None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _norm_designation(value: Any) -> str:
    return _text(value).lower()


def designations_agree(a: str, b: str) -> bool:
    a, b = _norm_designation(a), _norm_designation(b)
    if a == b:
        return True
    return a in _UNAVAILABLE_GROUP and b in _UNAVAILABLE_GROUP


# --------------------------------------------------------------------------
# 1. Canonical identity
# --------------------------------------------------------------------------


class IdentityResolver:
    """Cross-platform ids from the Sleeper player dump plus (optionally) the
    DynastyProcess id table. An id is returned only when it is unambiguous:
    sources that disagree, or one platform id shared by several players, give
    null with a reason."""

    def __init__(
        self,
        sleeper_dump: Mapping[str, Any] | None = None,
        dp_rows: Mapping[str, Mapping[str, Any]] | None = None,
        *,
        dp_unavailable_reason: str | None = None,
    ):
        self._dump = {str(k): v for k, v in (sleeper_dump or {}).items() if isinstance(v, Mapping)}
        self._dp = {str(k): v for k, v in (dp_rows or {}).items() if isinstance(v, Mapping)}
        self._dp_reason = dp_unavailable_reason if not self._dp else None
        self._owners: dict[tuple[str, str], set[str]] = {}
        for name, (sleeper_key, dp_key) in ID_FIELDS.items():
            for sid, rec in self._dump.items():
                value = _clean_id(rec.get(sleeper_key)) if sleeper_key else ""
                if value:
                    self._owners.setdefault((name, value), set()).add(sid)
            for sid, rec in self._dp.items():
                value = _clean_id(rec.get(dp_key)) if dp_key else ""
                if value:
                    self._owners.setdefault((name, value), set()).add(sid)

    def _field(self, name: str, sid: str) -> tuple[str | None, str | None, str | None]:
        """-> (value, source, reason)."""

        sleeper_key, dp_key = ID_FIELDS[name]
        candidates: list[tuple[str, str]] = []
        if sleeper_key and sid in self._dump:
            value = _clean_id(self._dump[sid].get(sleeper_key))
            if value:
                candidates.append((value, "sleeper_player_directory"))
        if dp_key and sid in self._dp:
            value = _clean_id(self._dp[sid].get(dp_key))
            if value:
                candidates.append((value, "dynastyprocess_db_playerids"))
        if not candidates:
            if dp_key and not sleeper_key and self._dp_reason:
                return None, None, self._dp_reason
            if sid not in self._dump and sid not in self._dp:
                return None, None, "player_not_in_crosswalk_sources"
            return None, None, "id_not_mapped_in_sources"
        if len({v for v, _ in candidates}) > 1:
            return None, None, "sources_disagree"
        value, source = candidates[0]
        if name == "gsis_id" and not _GSIS_RE.match(value):
            return None, None, "gsis_malformed"
        if len(self._owners.get((name, value), {sid})) > 1:
            return None, None, "id_shared_by_multiple_players"
        sources = sorted({s for _, s in candidates})
        return value, "+".join(sources), None

    def resolve(self, player_id: Any, *, name: Any = None, team: Any = None, position: Any = None) -> dict[str, Any]:
        sid = _clean_id(player_id)
        ids: dict[str, str | None] = {"sleeper_id": sid or None}
        sources: dict[str, str] = {"sleeper_id": "sleeper_player_directory"} if sid else {}
        reasons: dict[str, str] = {} if sid else {"sleeper_id": "player_id_missing"}
        for field_name in ID_FIELDS:
            value, source, reason = self._field(field_name, sid)
            ids[field_name] = value
            if value is not None and source:
                sources[field_name] = source
            if reason:
                reasons[field_name] = reason
        return {
            "player_id": sid or None,
            "id_namespace": "sleeper",
            "name": _text(name) or None,
            "team": _text(team) or None,
            "position": _text(position) or None,
            "ids": ids,
            "id_sources": sources,
            "ids_unavailable_reasons": reasons,
        }


# --------------------------------------------------------------------------
# 2. Evidence context (everything the builders may read)
# --------------------------------------------------------------------------


def _week_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


class OfficialIndex:
    """Official weekly NFL injury-report rows for one season."""

    def __init__(self, rows: Sequence[Mapping[str, Any]], season: int):
        self.season = season
        self.by_sleeper: dict[str, dict[int, list[Mapping[str, Any]]]] = {}
        self.by_gsis: dict[str, dict[int, list[Mapping[str, Any]]]] = {}
        self.latest_week: int | None = None
        for row in rows:
            if _text(row.get("season")) != str(season) or _text(row.get("season_type")).upper() not in ("", "REG"):
                continue
            week = _week_int(row.get("week"))
            if week is None:
                continue
            self.latest_week = week if self.latest_week is None else max(self.latest_week, week)
            for index, key in ((self.by_sleeper, "sleeper_id"), (self.by_gsis, "gsis_id")):
                ident = _text(row.get(key))
                if ident:
                    index.setdefault(ident, {}).setdefault(week, []).append(row)

    def rows_for(self, sleeper_id: str | None, gsis_id: str | None, week: int) -> list[Mapping[str, Any]]:
        found: list[Mapping[str, Any]] = []
        for index, ident in ((self.by_sleeper, sleeper_id), (self.by_gsis, gsis_id)):
            for row in index.get(ident or "", {}).get(week, []):
                if not any(row is f for f in found):
                    found.append(row)
        return found


@dataclass
class EvidenceContext:
    now: datetime
    clock_season: int | None = None
    clock_week: int | None = None
    clock_phase: str | None = None
    identity: IdentityResolver = field(default_factory=IdentityResolver)
    official: OfficialIndex | None = None
    official_unavailable_reason: str | None = "official_reports_not_loaded"
    observations: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    observations_unavailable_reason: str | None = "status_change_log_not_loaded"
    news: dict[str, list[Mapping[str, Any]]] = field(default_factory=dict)
    news_unavailable_reason: str | None = "news_store_not_loaded"

    @classmethod
    def empty(cls, now: datetime) -> "EvidenceContext":
        return cls(now=now)


# --------------------------------------------------------------------------
# 3. Availability provenance
# --------------------------------------------------------------------------


def _source_row(
    source_type: str,
    *,
    source_name: str,
    source_url: str | None,
    is_official: bool,
    status: str | None,
    designation: str | None,
    observed_at: str | None,
    verified_at: str | None,
    source_published_at: str | None,
    unavailable: Mapping[str, str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    assert source_type in SOURCE_TYPES
    reasons = dict(unavailable or {})
    if source_url is None:
        reasons.setdefault("source_url", "no_url_stored_for_this_source")
    return {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": source_url,
        "is_official": bool(is_official),
        "status": status,
        "designation": designation,
        "observed_at": observed_at,
        "verified_at": verified_at,
        "source_published_at": source_published_at,
        "unavailable_reasons": reasons,
        **extra,
    }


def _official_source(rows: Sequence[Mapping[str, Any]], season: int, week: int) -> tuple[dict[str, Any] | None, bool]:
    """-> (source row, rows_conflict). Several rows for one player-week are
    merged only when they agree on the designation."""

    if not rows:
        return None, False
    designations = {_text(r.get("report_status")) for r in rows if _text(r.get("report_status"))}
    conflict = len(designations) > 1
    rows = sorted(rows, key=lambda r: (_text(r.get("date_modified")), _text(r.get("report_status"))))
    row = rows[-1]
    designation = _text(row.get("report_status")) or None
    stamped = parse_ts(_text(row.get("date_modified")))
    reasons: dict[str, str] = {"observed_at": "ingest_time_not_recorded"}
    if stamped is None:
        reasons["verified_at"] = "report_row_has_no_date_modified"
        reasons["source_published_at"] = "report_row_has_no_date_modified"
    if designation is None:
        reasons["designation"] = "report_row_has_practice_status_only"
    return (
        _source_row(
            "official_team_report",
            source_name=OFFICIAL_SOURCE_NAME,
            source_url=OFFICIAL_URL_TEMPLATE.format(season=season),
            is_official=True,
            status=designation,
            designation=_norm_designation(designation) or None,
            observed_at=None,
            verified_at=_iso(stamped) if stamped else None,
            source_published_at=_iso(stamped) if stamped else None,
            unavailable=reasons,
            practice_status=_text(row.get("practice_status")) or None,
            injury=_text(row.get("report_primary_injury") or row.get("practice_primary_injury")) or None,
            report_week=_week_int(row.get("week")),
            rows_conflict=conflict,
        ),
        conflict,
    )


def build_availability(
    row: Mapping[str, Any],
    identity: Mapping[str, Any],
    ctx: EvidenceContext,
    *,
    season: int | None,
    week: int | None,
    game_id: str | None = None,
) -> dict[str, Any]:
    """Injury/status provenance for one player and one game week."""

    pid = _text(identity.get("player_id")) or None
    gsis = (identity.get("ids") or {}).get("gsis_id")
    sources: list[dict[str, Any]] = []
    notes: dict[str, str] = {}
    skipped: dict[str, str] = {}

    # official NFL report for exactly this season/week
    official_src: dict[str, Any] | None = None
    if season is None or week is None:
        skipped["official_team_report"] = "no_regular_season_week_to_look_up"
    elif ctx.official is None or ctx.official.season != season:
        skipped["official_team_report"] = ctx.official_unavailable_reason or "official_reports_not_loaded_for_season"
    else:
        official_src, _ = _official_source(ctx.official.rows_for(pid, gsis, week), season, week)
        if official_src is None:
            latest = ctx.official.latest_week
            skipped["official_team_report"] = (
                "no_official_report_row_for_player_this_week"
                if latest is not None and latest >= week
                else f"official_reports_loaded_through_week_{latest}_not_yet_week_{week}"
            )
    if official_src:
        sources.append(official_src)

    # platform (Sleeper) status: current state only, so it applies to the clock week
    designation = _text(row.get("injury_status"))
    platform_applies = season is not None and week is not None and season == ctx.clock_season and week == ctx.clock_week
    if designation:
        if platform_applies:
            obs = ctx.observations.get(pid or "")
            observed_at = None
            reasons: dict[str, str] = {"verified_at": "platform_status_is_not_independently_verified"}
            if obs and _norm_designation(obs.get("injury_status")) == _norm_designation(designation) and parse_ts(obs.get("captured_at")):
                observed_at = _iso(parse_ts(obs.get("captured_at")))  # type: ignore[arg-type]
            else:
                reasons["observed_at"] = ctx.observations_unavailable_reason or "no_matching_status_change_event_recorded"
            reasons["source_published_at"] = "sleeper_does_not_publish_a_status_timestamp"
            sources.append(
                _source_row(
                    "platform_status",
                    source_name=PLATFORM_SOURCE_NAME,
                    source_url=None,
                    is_official=False,
                    status=designation,
                    designation=_norm_designation(designation),
                    observed_at=observed_at,
                    verified_at=None,
                    source_published_at=None,
                    unavailable=reasons,
                    injury=_text(obs.get("body_part")) or None if obs else None,
                    observed_at_meaning="first time our sync recorded this designation, not the time of the last check",
                )
            )
        else:
            skipped["platform_status"] = "platform_status_is_current_state_and_does_not_apply_to_the_requested_week"

    # news headlines that talk about this player's availability
    news_items = ctx.news.get(pid or "", []) if pid else []
    for n in news_items:
        pub = parse_ts(n.get("published_ts"))
        seen = parse_ts(n.get("first_seen_at"))
        sources.append(
            _source_row(
                "news_report",
                source_name=_text(n.get("publisher_domain")) or "news_feed",
                source_url=_text(n.get("url")) or None,
                is_official=False,
                status=None,
                designation=None,
                observed_at=_iso(seen) if seen else None,
                verified_at=None,
                source_published_at=_iso(pub) if pub else None,
                unavailable={
                    "verified_at": "headline_only_article_not_fetched",
                    "designation": "news_headlines_are_not_parsed_into_a_designation",
                },
                headline=_text(n.get("headline")) or None,
                event_type=_text(n.get("event_type")) or None,
                speculative=bool(n.get("speculative")),
            )
        )
    if not news_items and ctx.news_unavailable_reason:
        skipped["news_report"] = ctx.news_unavailable_reason
    elif not news_items:
        skipped["news_report"] = "no_recent_availability_headline_matched_this_player"

    primary = next((s for s in sources if s["source_type"] == "official_team_report" and s["designation"]), None)
    primary = primary or next((s for s in sources if s["source_type"] == "platform_status"), None)
    block: dict[str, Any] = {
        "status": primary["status"] if primary else None,
        "designation": primary["designation"] if primary else None,
        "practice_status": official_src.get("practice_status") if official_src else None,
        "applies_to": {"season": season, "week": week, "game_id": game_id},
        "source_type": primary["source_type"] if primary else None,
        "source_name": primary["source_name"] if primary else None,
        "source_url": primary["source_url"] if primary else None,
        "is_official": bool(primary and primary["is_official"]),
        "observed_at": primary["observed_at"] if primary else None,
        "verified_at": primary["verified_at"] if primary else None,
        "source_published_at": primary["source_published_at"] if primary else None,
        "sources": sources,
        "sources_not_available": skipped,
        "unavailable_reason": None,
    }
    if game_id is None:
        notes["game_id"] = "game_not_resolved_for_this_endpoint"
    if notes:
        block["applies_to_unavailable_reasons"] = notes
    if primary is None:
        block["unavailable_reason"] = (
            "No designation is on record from a source that applies to this week. "
            "The absence of a designation is not evidence the player is healthy."
        )
    return block


# --------------------------------------------------------------------------
# 4. Claims
# --------------------------------------------------------------------------


def _stable(*parts: object) -> str:
    import hashlib

    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]


def _evidence_from_source(src: Mapping[str, Any]) -> dict[str, Any]:
    ts = src.get("source_published_at") or src.get("observed_at")
    kind = "source_published_at" if src.get("source_published_at") else ("observed_at" if src.get("observed_at") else None)
    out = {
        "source_type": src["source_type"],
        "source": src["source_name"],
        "url": src.get("source_url"),
        "timestamp": ts,
        "timestamp_kind": kind,
        "is_official": bool(src.get("is_official")),
        "detail": src.get("status") or src.get("headline"),
    }
    if ts is None:
        out["timestamp_unavailable_reason"] = (src.get("unavailable_reasons") or {}).get(
            "source_published_at", "timestamp_not_recorded"
        )
    if src["source_type"] == "news_report":
        out["speculative"] = bool(src.get("speculative"))
    return out


def has_official_evidence(evidence: Sequence[Mapping[str, Any]]) -> bool:
    return any(e.get("is_official") and e.get("source_type") == "official_team_report" for e in evidence)


def finalize_claim(
    *,
    claim_type: str,
    subject_id: str | None,
    claim_text: str,
    claim_status: str,
    evidence: Sequence[Mapping[str, Any]],
    method: str,
    confidence: str,
    required_for_auto_publish: bool,
    now: datetime,
    applies_week: int | None = None,
    clock_week: int | None = None,
    clock_phase: str | None = None,
    extra_blockers: Sequence[str] = (),
    unavailable_reason: str | None = None,
) -> dict[str, Any]:
    """The only place a claim gets its status and eligibility.

    ``confirmed`` is downgraded to ``reported`` unless official evidence is
    present, and ``auto_publish_eligible`` is derived, never passed in."""

    if claim_status not in CLAIM_STATUSES:
        raise ValueError(f"claim_status must be one of {CLAIM_STATUSES}")
    if claim_status == "confirmed" and not has_official_evidence(evidence):
        claim_status = "reported"
    blockers: list[str] = list(extra_blockers)
    age_hours: float | None = None
    fresh: bool | None = None
    if claim_status != "confirmed":
        blockers.append("claim_not_confirmed")
    else:
        official = [e for e in evidence if e.get("is_official") and e.get("source_type") == "official_team_report"]
        stamped = max((t for t in (parse_ts(e.get("timestamp")) for e in official) if t), default=None)
        if stamped is None:
            blockers.append("official_source_timestamp_unavailable")
        else:
            delta = now - stamped
            if delta < -FUTURE_TOLERANCE:
                blockers.append("official_source_timestamp_in_future")
                fresh = False
            else:
                age_hours = round(max(0.0, delta.total_seconds()) / 3600.0, 1)
                fresh = age_hours <= AUTO_PUBLISH_FRESH_HOURS
                if not fresh:
                    blockers.append("official_source_older_than_freshness_window")
        if clock_phase is not None and clock_phase != "regular":
            blockers.append("season_phase_not_regular")
        if applies_week is not None and clock_week is not None and applies_week != clock_week:
            blockers.append("claim_week_is_not_the_current_week")
    eligible = claim_status == "confirmed" and not blockers
    return {
        "claim_id": _stable(claim_type, subject_id, claim_text, applies_week),
        "claim_type": claim_type,
        "subject_player_id": subject_id,
        "claim_text": claim_text,
        "claim_status": claim_status,
        "evidence": [dict(e) for e in evidence],
        "method": method,
        "confidence": confidence,
        "required_for_auto_publish": bool(required_for_auto_publish),
        "auto_publish_eligible": bool(eligible),
        "auto_publish": {
            "freshness_window_hours": AUTO_PUBLISH_FRESH_HOURS,
            "evidence_age_hours": age_hours,
            "fresh": fresh,
            "blockers": blockers,
        },
        "unavailable_reason": unavailable_reason,
    }


def _label(identity: Mapping[str, Any]) -> str:
    bits = ", ".join(b for b in (identity.get("position"), identity.get("team")) if b)
    return f"{identity.get('name') or 'Player ' + str(identity.get('player_id'))}" + (f" ({bits})" if bits else "")


def build_availability_claim(
    availability: Mapping[str, Any],
    identity: Mapping[str, Any],
    ctx: EvidenceContext,
    *,
    required: bool = True,
) -> tuple[dict[str, Any] | None, str | None]:
    """The availability-designation claim for one player-week, or
    ``(None, reason)`` when no source supports one."""

    applies = availability.get("applies_to") or {}
    season, week = applies.get("season"), applies.get("week")
    sources = list(availability.get("sources") or [])
    official = next((s for s in sources if s["source_type"] == "official_team_report" and s.get("designation")), None)
    platform = next((s for s in sources if s["source_type"] == "platform_status"), None)
    news = [s for s in sources if s["source_type"] == "news_report"]
    label = _label(identity)
    when = f"{season} week {week}" if season and week else "the requested week"

    if official is None and platform is None and not news:
        return None, availability.get("unavailable_reason") or "no_source_supports_an_availability_claim"

    blockers: list[str] = []
    if official is not None:
        evidence = [_evidence_from_source(official)]
        status = "confirmed"
        confidence = "high"
        method = "official_report_lookup"
        text = f"{label} is listed {official['status']} for {when} on the official NFL injury report."
        if official.get("rows_conflict"):
            status, confidence = "reported", "low"
            blockers.append("official_rows_disagree")
            text = f"{label} has conflicting official NFL report rows for {when}; no designation is asserted."
        if platform is not None:
            evidence.append(_evidence_from_source(platform))
            if not designations_agree(official["designation"], platform["designation"]):
                status, confidence = "reported", "low"
                blockers.append("sources_disagree")
                text = (
                    f"{label} is listed {official['status']} on the official NFL report for {when}, but Sleeper shows "
                    f"{platform['status']}; the sources disagree and nothing is asserted."
                )
        evidence += [_evidence_from_source(n) for n in news]
    elif platform is not None:
        evidence = [_evidence_from_source(platform)] + [_evidence_from_source(n) for n in news]
        status = "reported"
        confidence = "medium"
        method = "platform_status_lookup"
        text = (
            f"{label} is listed {platform['status']} for {when} on Sleeper's player status. "
            "No official NFL report row is on file for this week, so this is not confirmed."
        )
    else:
        evidence = [_evidence_from_source(n) for n in news]
        speculative_only = all(bool(n.get("speculative")) for n in news)
        status = "unverified" if speculative_only else "reported"
        confidence = "low"
        method = "news_headline_match"
        first = news[0]
        text = (
            f"A news headline discusses {label}'s availability for {when} ({first.get('headline') or 'headline'}); "
            "the article was not fetched and no designation is asserted."
        )
    claim = finalize_claim(
        claim_type="availability_designation",
        subject_id=identity.get("player_id"),
        claim_text=text,
        claim_status=status,
        evidence=evidence,
        method=method,
        confidence=confidence,
        required_for_auto_publish=required,
        now=ctx.now,
        applies_week=week,
        clock_week=ctx.clock_week,
        clock_phase=ctx.clock_phase,
        extra_blockers=blockers,
    )
    return claim, None


def roll_up(claims: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Item-level auto-publish fields from the claims marked required."""

    required = [c for c in claims if c.get("required_for_auto_publish")]
    blockers: list[str] = []
    if not required:
        blockers.append("no_confirmable_claim_for_this_item")
    for c in required:
        if not c["auto_publish_eligible"]:
            blockers.extend(f"{c['claim_type']}:{b}" for b in c["auto_publish"]["blockers"])
    return {
        "auto_publish_eligible": bool(required) and all(c["auto_publish_eligible"] for c in required),
        "auto_publish_blockers": sorted(set(blockers)),
        "auto_publish_freshness_window_hours": AUTO_PUBLISH_FRESH_HOURS,
    }
