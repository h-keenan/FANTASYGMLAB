"""Canonical Alerts presentation: source truth, FantasyGM read, toast tier.

Does not fetch providers, scrape articles, or mutate valuation columns.
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from modules import news_intelligence as ni

IMPACT_OPPORTUNITY_RISING = "opportunity_rising"
IMPACT_OPPORTUNITY_FALLING = "opportunity_falling"
IMPACT_ROLE_UNCERTAIN = "role_uncertain"
IMPACT_INJURY_REPLACEMENT = "injury_replacement_opportunity"
IMPACT_TEAM_CHANGE = "team_change"
IMPACT_STARTER_AVAILABILITY = "starter_availability_impact"
IMPACT_MONITOR = "monitor"

TOAST_CRITICAL = "critical"
TOAST_HIGH = "high"
TOAST_IMPORTANT = "important"
TOAST_INFORMATIONAL = "informational"

UNAVAILABLE_INJURY_STATUSES = frozenset(
    {
        "ir",
        "pup",
        "nfi",
        "out",
        "injured reserve",
        "injured_reserve",
        "doubtful",
        "suspension",
        "suspended",
    }
)
_MY_REL = frozenset({"MY_STARTER", "MY_BENCH", "MY_TAXI", "MY_IR"})


def safe_source_url(value: object) -> str:
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    return candidate if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else ""


_TRACKING_QUERY_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "gclsrc",
        "dclid",
        "mc_cid",
        "mc_eid",
        "_hsenc",
        "_hsmi",
        "igshid",
        "si",
        "feature",
        "ref",
        "ref_src",
        "cmp",
        "cmpid",
        "cid",
        "ncid",
        "ocid",
        "yptr",
        "sr_share",
        "share",
        "source",
    }
)
_REL_PRECEDENCE = {
    "MY_STARTER": 80,
    "MY_BENCH": 70,
    "MY_TAXI": 60,
    "MY_IR": 50,
    "OPPONENT_ROSTER": 30,
    "FREE_AGENT": 20,
    "UNKNOWN": 0,
    "": 0,
}
_SEV_PRECEDENCE = {
    "CRITICAL": 40,
    "HIGH": 30,
    "MEDIUM": 20,
    "LOW": 10,
    "NONE": 0,
    "": 0,
}


def normalize_article_url(value: object) -> str:
    """Drop tracking noise so equivalent provider URLs share one article id."""

    candidate = safe_source_url(value)
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    host = str(parsed.netloc or "").strip().casefold()
    if host.startswith("www."):
        host = host[4:]
    kept: list[tuple[str, str]] = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = str(key or "").strip().casefold()
        if not lowered or lowered.startswith("utm_") or lowered in _TRACKING_QUERY_KEYS:
            continue
        kept.append((key, val))
    path = str(parsed.path or "").rstrip("/") or "/"
    query = urlencode(kept, doseq=True)
    return urlunparse((str(parsed.scheme or "https").casefold(), host, path, "", query, ""))


def _normalized_headline(row: Mapping[str, Any] | None) -> str:
    if not isinstance(row, Mapping):
        return ""
    title = str(
        row.get("news_article_title")
        or row.get("article_title")
        or row.get("source_headline")
        or row.get("title")
        or row.get("headline")
        or row.get("value")
        or ""
    ).strip()
    return re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()


def _publication_bucket(row: Mapping[str, Any] | None) -> str:
    if not isinstance(row, Mapping):
        return "0"
    raw = (
        row.get("event_time")
        or row.get("news_event_time")
        or row.get("published_ts")
        or row.get("article_time")
        or 0
    )
    try:
        ts = float(raw)
    except (TypeError, ValueError):
        ts = 0.0
    return str(int(ts // 86400) if ts > 0 else 0)


def canonical_article_identity(row: Mapping[str, Any] | None) -> str:
    """Exact-source-article id. Not player-specific. Not a family rec id."""

    if not isinstance(row, Mapping):
        return ""
    stored = str(row.get("article_identity") or "").strip()
    if stored.startswith("article:"):
        return stored
    guid = str(
        row.get("guid") or row.get("article_guid") or row.get("provider_article_id") or ""
    ).strip()
    if guid and guid.lower() not in {"none", "null"}:
        guid_url = normalize_article_url(guid)
        seed = guid_url or re.sub(r"\s+", " ", guid.casefold()).strip()
        if seed and not seed.startswith("news:") and not is_collapsing_family_recommendation_id(seed):
            return "article:" + hashlib.sha1(f"guid|{seed}".encode("utf-8")).hexdigest()
    url = normalize_article_url(row.get("source_url") or row.get("link") or row.get("canonical_url"))
    if url:
        return "article:" + hashlib.sha1(url.encode("utf-8")).hexdigest()
    source = re.sub(r"\s+", " ", str(row.get("source") or row.get("news_source") or "").casefold()).strip()
    headline = _normalized_headline(row)
    if source and headline:
        seed = f"{source}|{headline}|{_publication_bucket(row)}"
        return "article:" + hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return ""


def _relationship_rank(row: Mapping[str, Any]) -> int:
    rel = str(row.get("roster_relationship") or row.get("news_roster_relationship") or "").strip().upper()
    kind = str(row.get("relationship_kind") or "").strip().upper()
    score = _REL_PRECEDENCE.get(rel, 0)
    if rel in _MY_REL or kind == "MY_PLAYER":
        score += 50
    elif kind == "MY_TEAMMATE":
        score += 12
    if str(row.get("player_id") or "").strip():
        score += 4
    return score


def _severity_rank(row: Mapping[str, Any]) -> int:
    sev = str(row.get("severity") or row.get("news_event_severity") or "").strip().upper()
    return _SEV_PRECEDENCE.get(sev, 0)


def _event_time_value(row: Mapping[str, Any]) -> float:
    raw = row.get("event_time") or row.get("news_event_time") or row.get("published_ts") or 0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _unique_context(*parts: object) -> str:
    seen: set[str] = set()
    kept: list[str] = []
    for part in parts:
        text = str(part or "").strip()
        if not text:
            continue
        key = re.sub(r"\s+", " ", text.casefold())
        if key in seen:
            continue
        seen.add(key)
        kept.append(text)
    return " ".join(kept)[:220]


def _collect_player_ids(*rows: Mapping[str, Any]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in (
            "player_id",
            "beneficiary_player_id",
            "affected_player_ids",
            "beneficiary_player_ids",
        ):
            value = row.get(key)
            items = value if isinstance(value, (list, tuple, set)) else (value,)
            for item in items:
                pid = str(item or "").strip()
                if pid and pid not in seen:
                    seen.add(pid)
                    ordered.append(pid)
    return tuple(ordered)


def merge_article_row(primary: Mapping[str, Any], secondary: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministically merge two rows for the same physical source article."""

    left = dict(primary)
    right = dict(secondary)
    left_rank = (
        _relationship_rank(left),
        1 if str(left.get("relationship_kind") or "") == "MY_PLAYER" else 0,
        _severity_rank(left),
        _event_time_value(left),
    )
    right_rank = (
        _relationship_rank(right),
        1 if str(right.get("relationship_kind") or "") == "MY_PLAYER" else 0,
        _severity_rank(right),
        _event_time_value(right),
    )
    winner, other = (left, right) if left_rank >= right_rank else (right, left)
    merged = dict(winner)
    article = canonical_article_identity(winner) or canonical_article_identity(other)
    if article:
        merged["article_identity"] = article
        merged["id"] = f"news:{article}"
    url = normalize_article_url(winner.get("source_url") or winner.get("link")) or normalize_article_url(
        other.get("source_url") or other.get("link")
    )
    if url:
        merged["source_url"] = url
        merged["canonical_url"] = url
    if _event_time_value(other) > _event_time_value(winner):
        merged["event_time"] = other.get("event_time") or other.get("news_event_time")
        merged["news_event_time"] = other.get("news_event_time") or other.get("event_time")
    if _severity_rank(other) > _severity_rank(winner):
        merged["severity"] = other.get("severity") or other.get("news_event_severity")
        merged["news_event_severity"] = other.get("news_event_severity") or other.get("severity")
    merged["fantasygm_read"] = _unique_context(
        winner.get("fantasygm_read"), other.get("fantasygm_read")
    )
    merged["context"] = _unique_context(winner.get("context"), other.get("context"), merged.get("fantasygm_read"))
    players = _collect_player_ids(winner, other)
    if players:
        merged["affected_player_ids"] = players
        if not str(merged.get("player_id") or "").strip():
            merged["player_id"] = players[0]
        extra = tuple(pid for pid in players if pid != str(merged.get("player_id") or "").strip())
        if extra:
            merged["beneficiary_player_ids"] = extra
            if not str(merged.get("beneficiary_player_id") or "").strip():
                merged["beneficiary_player_id"] = extra[0]
    aliases: list[str] = []
    seen_alias: set[str] = set()
    for row in (winner, other):
        for key in ("event_identity", "news_event_identity", "id", "recommendation_id"):
            text = str(row.get(key) or "").strip()
            if text and text not in seen_alias:
                seen_alias.add(text)
                aliases.append(text)
        extra_aliases = row.get("event_identity_aliases")
        if isinstance(extra_aliases, (list, tuple)):
            for item in extra_aliases:
                text = str(item or "").strip()
                if text and text not in seen_alias:
                    seen_alias.add(text)
                    aliases.append(text)
    if bool(winner.get("significant_injury_event") or other.get("significant_injury_event") or winner.get("news_significant_injury_event") or other.get("news_significant_injury_event")):
        merged["significant_injury_event"] = True
        merged["news_significant_injury_event"] = True
    merged["event_identity_aliases"] = tuple(aliases)
    if bool(winner.get("dismissed")) or bool(other.get("dismissed")):
        merged["dismissed"] = True
        merged["unread"] = False
        merged["has_explicit_dismiss_state"] = True
    elif bool(winner.get("has_explicit_read_state")) or bool(other.get("has_explicit_read_state")) or (
        winner.get("unread") is False or other.get("unread") is False
    ):
        if winner.get("unread") is False or other.get("unread") is False or winner.get("has_explicit_read_state") or other.get("has_explicit_read_state"):
            merged["unread"] = False
            merged["has_explicit_read_state"] = True
    return merged


def merge_exact_article_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    """Collapse the same physical article before cap / inventory / toast."""

    started = time.perf_counter()
    incoming = [dict(row) for row in rows if isinstance(row, Mapping)]
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    passthrough: list[dict[str, Any]] = []
    alias_extras = 0
    for row in incoming:
        key = canonical_article_identity(row)
        if not key:
            passthrough.append(row)
            continue
        row["article_identity"] = key
        if key not in grouped:
            grouped[key] = row
            order.append(key)
            continue
        alias_extras += 1
        grouped[key] = merge_article_row(grouped[key], row)
    merged = [grouped[key] for key in order] + passthrough
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return tuple(merged), {
        "pre_dedupe_event_count": len(incoming),
        "post_dedupe_event_count": len(merged),
        "duplicate_article_count": max(0, len(incoming) - len(merged)),
        "duplicate_identity_alias_count": alias_extras,
        "dedupe_ms": elapsed,
    }


_FAMILY_RECOMMENDATION_ID = re.compile(r"^news-event:[^:]+:[^:]+$")


def is_collapsing_family_recommendation_id(value: object) -> bool:
    """True for player/family keys that many distinct articles can share."""

    text = str(value or "").strip()
    if text.startswith("rec:"):
        text = text[4:]
    if not text:
        return False
    if text.startswith("news-event:unknown:") or text.startswith("news-event::"):
        return True
    return bool(_FAMILY_RECOMMENDATION_ID.match(text))


def canonical_alert_identity(row: Mapping[str, Any] | None) -> str:
    """Unique per source article when a canonical article id exists."""

    if not isinstance(row, Mapping):
        return ""
    article = canonical_article_identity(row)
    if article:
        return article
    eid = str(row.get("event_identity") or row.get("news_event_identity") or "").strip()
    if eid and not is_collapsing_family_recommendation_id(eid):
        return eid
    url = str(row.get("source_url") or row.get("link") or "").strip()
    player = str(row.get("player_id") or "").strip()
    title = str(
        row.get("headline")
        or row.get("title")
        or row.get("news_article_title")
        or row.get("value")
        or ""
    ).strip()[:96]
    rec = str(row.get("recommendation_id") or "").strip()
    rid = str(row.get("id") or "").strip()
    seed = "|".join((eid, rec, rid, player, url, title))
    if not any((eid, rec, rid, player, url, title)):
        return ""
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def attention_aliases(row: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Read/dismiss keys for exactly one event.

    Family recommendation ids like ``news-event:{player}:injury_chain`` are
    omitted when a more specific ``event_identity`` exists so one action
    cannot mark every article in that family.
    """

    if not isinstance(row, Mapping):
        return ()
    keys: list[str] = []
    seen: set[str] = set()

    def add(raw: object) -> None:
        text = str(raw or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        keys.append(text)
        alias = text[4:] if text.startswith("rec:") else f"rec:{text}"
        if alias and alias not in seen:
            seen.add(alias)
            keys.append(alias)

    add(canonical_alert_identity(row))
    canonical = canonical_alert_identity(row)
    if canonical and not canonical.startswith("news:"):
        add(f"news:{canonical}")
    article = canonical_article_identity(row)
    if article:
        add(article)
        add(f"news:{article}")
    add(row.get("event_identity") or row.get("news_event_identity"))
    extra_aliases = row.get("event_identity_aliases")
    if isinstance(extra_aliases, (list, tuple)):
        for item in extra_aliases:
            add(item)
    rec = str(row.get("recommendation_id") or "").strip()
    rid = str(row.get("id") or "").strip()
    eid = str(row.get("event_identity") or row.get("news_event_identity") or "").strip()
    specific = bool(eid and eid != rec and not is_collapsing_family_recommendation_id(eid))
    if rid and not (specific and is_collapsing_family_recommendation_id(rid)):
        add(rid)
    if rec and not (specific and is_collapsing_family_recommendation_id(rec)):
        add(rec)
    return tuple(keys)


def event_dedupe_key(row: Mapping[str, Any]) -> str:
    """Stable identity from source/event/player/time — not a Streamlit widget key."""

    identity = canonical_alert_identity(row)
    if identity:
        return identity
    parts = (
        str(row.get("player_id") or "").strip(),
        str(row.get("event_type") or row.get("news_event_type") or "").strip(),
        str(row.get("source_url") or row.get("link") or "").strip(),
        str(row.get("event_time") or row.get("news_event_time") or "").strip(),
        str(row.get("headline") or row.get("title") or row.get("article_title") or "").strip()[:80],
    )
    return "|".join(parts)


def source_headline(event: ni.FootballEvent | Mapping[str, Any]) -> str:
    if isinstance(event, ni.FootballEvent):
        article = str(event.article_title or "").strip()
        who = str(event.player_name or "").strip()
        team = str(event.team or "").strip()
        etype = str(event.event_type or "").strip().upper()
    else:
        article = str(
            event.get("news_article_title")
            or event.get("article_title")
            or event.get("title")
            or event.get("value")
            or event.get("headline")
            or ""
        ).strip()
        who = str(event.get("player_name") or event.get("news_player_name") or "").strip()
        team = str(event.get("team") or event.get("matched_team") or "").strip()
        etype = str(event.get("event_type") or event.get("news_event_type") or "").strip().upper()
    if etype == ni.FT_TRADE and who:
        if team:
            return f"{who} traded to {team}"
        return article[:140] if article else f"{who} traded"
    if article:
        return article[:140]
    if who and etype and etype not in {ni.FT_OTHER, ""}:
        return f"{who}: {etype.replace('_', ' ').title()}"
    return who or "Update"


def toast_tier(
    *,
    severity: str,
    relationship: str,
    event_type: str,
    significant_injury: bool = False,
) -> str:
    rel = str(relationship or "").strip().upper()
    sev = str(severity or "").strip().upper()
    etype = str(event_type or "").strip().upper()
    mine = rel in _MY_REL
    if mine and sev == ni.SEV_CRITICAL:
        return TOAST_CRITICAL
    if mine and sev == ni.SEV_HIGH and etype in {
        ni.FT_TRADE,
        ni.FT_RELEASE,
        ni.FT_IR_PUP_NFI,
        ni.FT_INACTIVE,
        ni.FT_SUSPENSION,
        ni.FT_INJURY_SEVERITY_UPDATE,
    }:
        return TOAST_HIGH
    if mine and significant_injury and etype in {ni.FT_INJURY, ni.FT_IR_PUP_NFI, ni.FT_INACTIVE}:
        return TOAST_HIGH
    if mine and sev == ni.SEV_HIGH:
        return TOAST_IMPORTANT
    if mine and sev == ni.SEV_MEDIUM:
        return TOAST_IMPORTANT
    if sev in {ni.SEV_CRITICAL, ni.SEV_HIGH} and not mine:
        return TOAST_IMPORTANT
    return TOAST_INFORMATIONAL


def should_toast(tier: str) -> bool:
    return str(tier or "") in {TOAST_CRITICAL, TOAST_HIGH}


def relevance_score(row: Mapping[str, Any]) -> int:
    rel = str(row.get("roster_relationship") or "").strip().upper()
    sev = str(row.get("severity") or row.get("news_event_severity") or "").strip().upper()
    etype = str(row.get("event_type") or row.get("news_event_type") or "").strip().upper()
    score = 0
    if rel == "MY_STARTER":
        score += 80
    elif rel in _MY_REL:
        score += 60
    if sev == "CRITICAL":
        score += 40
    elif sev == "HIGH":
        score += 25
    elif sev == "MEDIUM":
        score += 10
    if etype in {ni.FT_TRADE, ni.FT_RELEASE, ni.FT_IR_PUP_NFI, ni.FT_INACTIVE, ni.FT_SUSPENSION}:
        score += 20
    if bool(row.get("significant_injury_event") or row.get("news_significant_injury_event")):
        score += 15
    if str(row.get("impact_code") or "") in {
        IMPACT_OPPORTUNITY_RISING,
        IMPACT_INJURY_REPLACEMENT,
        IMPACT_STARTER_AVAILABILITY,
    }:
        score += 18
    age = row.get("news_age_seconds")
    if age is None:
        age = row.get("age_seconds")
    try:
        seconds = int(age)
    except (TypeError, ValueError):
        seconds = -1
    if 0 <= seconds < 3600:
        score += 12
    elif 0 <= seconds < 6 * 3600:
        score += 6
    return score


def _status_unavailable(value: object) -> bool:
    text = str(value or "").strip().casefold()
    return any(token in text for token in UNAVAILABLE_INJURY_STATUSES)


def _player_row(frame: Any, player_id: str) -> Any | None:
    pid = str(player_id or "").strip()
    if not pid or frame is None or "player_id" not in getattr(frame, "columns", ()):
        return None
    rows = frame[frame["player_id"].astype(str) == pid]
    if rows.empty:
        return None
    return rows.iloc[0]


def teammate_opportunity_from_structured(
    event: ni.FootballEvent,
    players_df: Any | None,
    *,
    my_roster_ids: Iterable[str] | None = None,
) -> dict[str, str]:
    """Map a non-roster teammate event onto a rostered same-team/position player.

    Source identity stays on the article player. FantasyGM context may mention
    opportunity only from structured team/position/status — not article inference.
    """

    empty: dict[str, str] = {}
    mine = {str(x).strip() for x in (my_roster_ids or ()) if str(x).strip()}
    if not mine or players_df is None or getattr(players_df, "empty", True):
        return empty
    if "player_id" not in getattr(players_df, "columns", ()):
        return empty
    event_pid = str(event.player_id or "").strip()
    if event_pid and event_pid in mine:
        return empty
    etype = str(event.event_type or "").upper()
    if etype not in {
        ni.FT_TRADE,
        ni.FT_SIGNING,
        ni.FT_INJURY,
        ni.FT_IR_PUP_NFI,
        ni.FT_INACTIVE,
        ni.FT_INJURY_SEVERITY_UPDATE,
    }:
        return empty
    event_row = _player_row(players_df, event_pid)
    team_col = "team" if "team" in players_df.columns else ""
    pos_col = "position" if "position" in players_df.columns else ""
    team = str(event.team or "").strip()
    pos = ""
    if event_row is not None:
        if team_col:
            team = team or str(event_row.get(team_col) or "").strip()
        if pos_col:
            pos = str(event_row.get(pos_col) or "").strip()
    if not team or not pos or not team_col or not pos_col:
        return empty
    injury_col = "injury_status" if "injury_status" in players_df.columns else ""
    status_col = "status" if "status" in players_df.columns else ""
    event_unavailable = etype in {
        ni.FT_INJURY,
        ni.FT_IR_PUP_NFI,
        ni.FT_INACTIVE,
        ni.FT_INJURY_SEVERITY_UPDATE,
    }
    if event_row is not None and not event_unavailable:
        blob = " ".join(
            (
                str(event_row.get(injury_col) or "") if injury_col else "",
                str(event_row.get(status_col) or "") if status_col else "",
            )
        )
        event_unavailable = _status_unavailable(blob)
    peers = players_df[
        (players_df["player_id"].astype(str).isin(mine))
        & (players_df[team_col].astype(str).str.upper() == team.upper())
        & (players_df[pos_col].astype(str).str.upper() == pos.upper())
    ]
    if event_pid:
        peers = peers[peers["player_id"].astype(str) != event_pid]
    if peers.empty:
        return empty
    peers = peers.sort_values("player_id")
    beneficiary = peers.iloc[0]
    beneficiary_id = str(beneficiary.get("player_id") or "").strip()
    beneficiary_name = str(beneficiary.get("name") or "your player").strip()
    if not beneficiary_id:
        return empty
    if event_unavailable or etype in {ni.FT_INJURY, ni.FT_IR_PUP_NFI, ni.FT_INACTIVE}:
        return {
            "code": IMPACT_INJURY_REPLACEMENT,
            "read": (
                f"Opportunity may rise for {beneficiary_name}. Same-team {pos} "
                "teammate shows structured unavailability. Monitor usage — the "
                "article does not confirm a role change."
            ),
            "supported": "1",
            "beneficiary_player_id": beneficiary_id,
        }
    return {
        "code": IMPACT_MONITOR,
        "read": (
            f"Monitor {beneficiary_name}. A same-team {pos} teammate transaction "
            "was reported. Usage is unconfirmed."
        ),
        "supported": "1",
        "beneficiary_player_id": beneficiary_id,
    }


def structured_roster_impact(
    event: ni.FootballEvent,
    players_df: Any | None,
    *,
    my_roster_ids: Iterable[str] | None = None,
) -> dict[str, str]:
    """FantasyGM read from already-hydrated player/injury/team fields only."""

    empty = {"code": IMPACT_MONITOR, "read": "", "supported": "0"}
    teammate = teammate_opportunity_from_structured(
        event, players_df, my_roster_ids=my_roster_ids
    )
    if teammate:
        return teammate
    if players_df is None or getattr(players_df, "empty", True):
        return empty
    if "player_id" not in getattr(players_df, "columns", ()):
        return empty
    etype = str(event.event_type or "").upper()
    team = str(event.team or "").strip()
    player_id = str(event.player_id or "").strip()
    if etype in {ni.FT_TRADE, ni.FT_SIGNING} and not team:
        # Do not invent a destination from the headline.
        return {
            "code": IMPACT_TEAM_CHANGE,
            "read": "Team change reported. Role confirmation is still pending.",
            "supported": "1",
        }
    if etype in {ni.FT_TRADE, ni.FT_SIGNING} and team:
        frame = players_df
        team_col = "team" if "team" in frame.columns else ""
        pos_col = "position" if "position" in frame.columns else ""
        my_pos = ""
        if player_id:
            mine = frame[frame["player_id"].astype(str) == player_id]
            if not mine.empty and pos_col:
                my_pos = str(mine.iloc[0].get("position") or "").strip()
        unavailable = 0
        if team_col:
            peers = frame[frame[team_col].astype(str).str.upper() == team.upper()]
            if my_pos and pos_col:
                peers = peers[peers[pos_col].astype(str).str.upper() == my_pos.upper()]
            if player_id:
                peers = peers[peers["player_id"].astype(str) != player_id]
            injury_col = "injury_status" if "injury_status" in frame.columns else ""
            status_col = "status" if "status" in frame.columns else ""
            for _, row in peers.iterrows():
                blob = " ".join(
                    (
                        str(row.get(injury_col) or "") if injury_col else "",
                        str(row.get(status_col) or "") if status_col else "",
                    )
                )
                if _status_unavailable(blob):
                    unavailable += 1
        if unavailable:
            pos_label = my_pos or "position"
            return {
                "code": IMPACT_OPPORTUNITY_RISING,
                "read": (
                    f"Opportunity may rise. {team}'s {pos_label} room currently shows "
                    f"{unavailable} player(s) unavailable in structured status. "
                    "Monitor role confirmation before changing valuation."
                ),
                "supported": "1",
            }
        return {
            "code": IMPACT_TEAM_CHANGE,
            "read": f"Team change to {team}. Role confirmation is still pending.",
            "supported": "1",
        }
    if etype in {ni.FT_INJURY, ni.FT_IR_PUP_NFI, ni.FT_INACTIVE} and event.roster_relationship in _MY_REL:
        return {
            "code": IMPACT_STARTER_AVAILABILITY if event.roster_relationship == "MY_STARTER" else IMPACT_MONITOR,
            "read": "Availability may change. Structured status is the confirmation source — not the article.",
            "supported": "1",
        }
    if etype in {ni.FT_ROLE_INCREASE, ni.FT_STARTER_CHANGE}:
        return {
            "code": IMPACT_ROLE_UNCERTAIN,
            "read": "Role may be expanding. Treat as unconfirmed until depth/status fields move.",
            "supported": "1",
        }
    if etype in {ni.FT_ROLE_DECREASE, ni.FT_RELEASE}:
        return {
            "code": IMPACT_OPPORTUNITY_FALLING,
            "read": "Role may be shrinking. Wait for structured depth/status before ranking changes.",
            "supported": "1",
        }
    return empty


def apply_presentation(
    alert: ni.NewsAlert,
    *,
    players_df: Any | None = None,
    my_roster_ids: Iterable[str] | None = None,
) -> ni.NewsAlert:
    event = getattr(alert, "event", None)
    if not isinstance(event, ni.FootballEvent):
        return alert
    impact = structured_roster_impact(
        alert.event, players_df, my_roster_ids=my_roster_ids
    )
    headline = source_headline(alert.event)
    why = str(impact.get("read") or "").strip() or alert.why_care
    if str(impact.get("supported") or "") != "1":
        # Keep existing why_care; never invent competition from a headline.
        why = alert.why_care
        impact = {"code": IMPACT_MONITOR, "read": why, "supported": "0"}
    event = ni.FootballEvent(
        **{
            **alert.event.as_dict(),
            "corroboration_note": why or alert.event.corroboration_note,
        }
    )
    return ni.NewsAlert(
        event=event,
        severity=alert.severity,
        should_alert=alert.should_alert,
        title=headline,
        body=alert.body,
        why_care=why,
        action_hint=alert.action_hint,
        league_relevance_note=alert.league_relevance_note,
        escalated_from=alert.escalated_from,
        suppressed_reason=alert.suppressed_reason,
    )


def enrich_tile(
    tile: Mapping[str, Any],
    *,
    players_df: Any | None = None,
    my_roster_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    payload = dict(tile)
    event = ni.FootballEvent(
        event_type=str(payload.get("news_event_type") or payload.get("event_type") or ""),
        player_name=str(payload.get("news_player_name") or payload.get("player_name") or ""),
        player_id=str(payload.get("player_id") or ""),
        team=str(payload.get("team") or payload.get("matched_team") or ""),
        article_title=str(payload.get("news_article_title") or payload.get("article_title") or payload.get("title") or ""),
        source=str(payload.get("news_source") or payload.get("source") or ""),
        source_url=str(payload.get("source_url") or payload.get("link") or ""),
        roster_relationship=str(payload.get("news_roster_relationship") or payload.get("roster_relationship") or ""),
        significant_injury_event=bool(payload.get("news_significant_injury_event")),
    )
    if players_df is not None:
        impact = structured_roster_impact(
            event, players_df, my_roster_ids=my_roster_ids
        )
    else:
        impact = {
            "code": str(payload.get("impact_code") or IMPACT_MONITOR),
            "read": str(payload.get("news_why_care") or payload.get("fantasygm_read") or ""),
            "supported": "1" if payload.get("news_why_care") else "0",
        }
    payload["headline"] = source_headline(event)
    payload["source_headline"] = payload["headline"]
    payload["impact_code"] = impact["code"]
    payload["fantasygm_read"] = impact["read"] or str(payload.get("news_why_care") or "")
    payload["toast_tier"] = toast_tier(
        severity=str(payload.get("news_event_severity") or payload.get("severity") or ""),
        relationship=str(payload.get("news_roster_relationship") or payload.get("roster_relationship") or ""),
        event_type=str(payload.get("news_event_type") or payload.get("event_type") or ""),
        significant_injury=bool(payload.get("news_significant_injury_event")),
    )
    payload["valuation_impact"] = "none_from_article"
    payload["source_url"] = safe_source_url(payload.get("source_url") or payload.get("link"))
    article = canonical_article_identity(payload)
    if article:
        payload["article_identity"] = article
    beneficiary = str(impact.get("beneficiary_player_id") or payload.get("beneficiary_player_id") or "").strip()
    if beneficiary:
        payload["beneficiary_player_id"] = beneficiary
    return payload


def apply_roster_context_to_row(
    row: Mapping[str, Any],
    *,
    context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(row)
    if not isinstance(context, Mapping):
        return payload
    player_id = str(payload.get("player_id") or "").strip()
    name = str(payload.get("player_name") or payload.get("headline") or "").strip().casefold()
    name_index = context.get("player_name_to_id") if isinstance(context.get("player_name_to_id"), Mapping) else {}
    if not player_id and name:
        player_id = str(name_index.get(name) or "").strip()
        if player_id:
            payload["player_id"] = player_id
    if not player_id:
        return payload
    rel = str(payload.get("roster_relationship") or "").strip().upper()
    if rel in _MY_REL:
        return payload
    starters = {str(x) for x in (context.get("starter_ids") or ())}
    taxi = {str(x) for x in (context.get("taxi_ids") or ())}
    ir = {str(x) for x in (context.get("ir_ids") or ())}
    mine = {str(x) for x in (context.get("my_roster_ids") or ())}
    opponents = {str(x) for x in (context.get("opponent_ids") or ())}
    if player_id in starters:
        payload["roster_relationship"] = ni.REL_MY_STARTER
    elif player_id in ir:
        payload["roster_relationship"] = ni.REL_MY_IR
    elif player_id in taxi:
        payload["roster_relationship"] = ni.REL_MY_TAXI
    elif player_id in mine:
        payload["roster_relationship"] = ni.REL_MY_BENCH
    elif player_id in opponents:
        payload["roster_relationship"] = ni.REL_OPPONENT_ROSTER
    return payload


def rank_timeline_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = [dict(row) for row in rows if isinstance(row, Mapping)]
    ranked.sort(key=lambda row: -relevance_score(row))
    return ranked
