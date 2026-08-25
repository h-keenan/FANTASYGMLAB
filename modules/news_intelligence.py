"""News → structured football events → roster-aware alerts.

Extends ``modules.news_signal`` without replacing it. Articles may produce
events and alerts; they must NEVER write player valuation columns.

Canonical ownership:
- Classification taxonomy: ``news_signal``
- Fine-grained football events + roster alerts: this module
- Alert delivery: Dashboard tiles → ``notification_center.publish_activity_inventory``
- Valuation inputs: structured Sleeper status/injury/depth only
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

import pandas as pd

from modules import news_signal
from modules import signal_freshness

# --- Fine-grained football event taxonomy -------------------------------------

FT_INJURY = "INJURY"
FT_INJURY_SEVERITY_UPDATE = "INJURY_SEVERITY_UPDATE"
FT_IR_PUP_NFI = "IR_PUP_NFI"
FT_RETURN_TO_PRACTICE = "RETURN_TO_PRACTICE"
FT_RETURN_TO_PLAY = "RETURN_TO_PLAY"
FT_INACTIVE = "INACTIVE"
FT_ACTIVE = "ACTIVE"
FT_STARTER_CHANGE = "STARTER_CHANGE"
FT_DEPTH_CHART_CHANGE = "DEPTH_CHART_CHANGE"
FT_ROLE_INCREASE = "ROLE_INCREASE"
FT_ROLE_DECREASE = "ROLE_DECREASE"
FT_POSITION_BATTLE = "POSITION_BATTLE"
FT_TRADE = "TRADE"
FT_SIGNING = "SIGNING"
FT_RELEASE = "RELEASE"
FT_SUSPENSION = "SUSPENSION"
FT_RETIREMENT = "RETIREMENT"
FT_OTHER = "OTHER"

# Roster relationships
REL_MY_STARTER = "MY_STARTER"
REL_MY_BENCH = "MY_BENCH"
REL_MY_TAXI = "MY_TAXI"
REL_MY_IR = "MY_IR"
REL_FREE_AGENT = "FREE_AGENT"
REL_OPPONENT_ROSTER = "OPPONENT_ROSTER"
REL_UNKNOWN = "UNKNOWN"

# Alert severities
SEV_CRITICAL = "CRITICAL"
SEV_HIGH = "HIGH"
SEV_MEDIUM = "MEDIUM"
SEV_LOW = "LOW"
SEV_NONE = "NONE"

EVIDENCE_STRUCTURED = "A_structured_state"
EVIDENCE_CONFIRMED = "B_confirmed_report"
EVIDENCE_BEAT = "C_beat_signal"
EVIDENCE_SPECULATION = "D_speculation"

ALERT_STATE_KEY = "_news_intelligence_alert_state"
ALERT_COOLDOWN_SECONDS = 6 * 3600
MAX_NEWS_ALERT_TILES = 3
TIMELINE_EVENT_KEY = "_news_intelligence_timeline_events"


def event_family_key(event_type: str) -> str:
    """Soft identity family for injury/role escalation chains."""

    family = str(event_type or "")
    if family in {FT_INJURY, FT_INACTIVE, FT_IR_PUP_NFI, FT_INJURY_SEVERITY_UPDATE}:
        return "injury_chain"
    if family in {
        FT_POSITION_BATTLE,
        FT_STARTER_CHANGE,
        FT_ROLE_INCREASE,
        FT_ROLE_DECREASE,
        FT_DEPTH_CHART_CHANGE,
    }:
        return "role_chain"
    return family or "other"

# Ephemeral presentation intelligence — independent of Game Plan football package.
PRESENTATION_DIGEST_KEY = "_news_intelligence_presentation_digest"
ROSTER_CONTEXT_KEY = "_news_intelligence_roster_context"
ROSTER_CONTEXT_PENDING_KEY = "_news_intelligence_roster_context_pending"
PRESENTATION_STATS_KEY = "_news_intelligence_presentation_stats"
NEWS_ALERT_LABEL = "News Alert"

# Valuation columns articles must never touch.
VALUATION_COLUMNS = frozenset(
    {
        "score",
        "base_score",
        "dynasty_score",
        "value_score",
        "rebuild_score",
        "league_dynasty_score",
        "league_value_score",
        "league_rebuild_score",
        "strategy_score",
        "news_factor",
        "risk_multiplier",
        "injury_multiplier",
        "league_settings_multiplier",
        "opportunity_score",
    }
)

_EVENT_PHRASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        FT_IR_PUP_NFI,
        (
            "placed on injured reserve",
            "placed on ir",
            "to injured reserve",
            "on injured reserve",
            "pup list",
            "physically unable to perform",
            "non-football injury",
            "nfi list",
        ),
    ),
    (
        FT_INACTIVE,
        ("ruled out", "will not play", "inactive for", "declared inactive", "out for sunday", "out for monday"),
    ),
    (
        FT_RETURN_TO_PLAY,
        (
            "activated from injured reserve",
            "activated from ir",
            "cleared to play",
            "will play",
            "listed as active",
            "is active for",
            "removed from injury report",
        ),
    ),
    (
        FT_RETURN_TO_PRACTICE,
        (
            "returned to practice",
            "return to practice",
            "full participant",
            "designated to return",
            "practiced fully",
        ),
    ),
    (
        FT_ACTIVE,
        ("listed as active", "is active", "active against"),
    ),
    (
        FT_STARTER_CHANGE,
        (
            "named the starter",
            "named starter",
            "named the starting",
            "officially named starter",
            "listed as the starter",
            "listed as starter",
            "will start at",
            "is starting at",
            "has been named the starter",
        ),
    ),
    (
        FT_POSITION_BATTLE,
        (
            "position battle",
            "competing for",
            "competition at",
            "open competition",
            "battle for the starting",
            "in the mix for",
        ),
    ),
    (
        FT_ROLE_INCREASE,
        (
            "taking first-team reps",
            "first-team reps",
            "working with the ones",
            "with the ones",
            "promoted to",
            "lead back",
            "feature back",
            "expanded role",
            "more snaps",
            "earning more snaps",
        ),
    ),
    (
        FT_ROLE_DECREASE,
        (
            "losing snaps",
            "demoted",
            "benched",
            "relegated to backup",
            "committee",
            "timeshare",
            "reduced role",
            "falling behind",
        ),
    ),
    (
        FT_DEPTH_CHART_CHANGE,
        ("depth chart", "moved up the depth chart", "moved down the depth chart", "listed as wr2", "listed as wr3", "listed as rb2"),
    ),
    (
        FT_TRADE,
        ("traded to", "acquired in a trade", "trade for", "has been traded"),
    ),
    (
        FT_SIGNING,
        ("signed by", "signed with", "agreed to terms", "agrees to terms"),
    ),
    (
        FT_RELEASE,
        ("released by", "waived by", "cut by", "has been released"),
    ),
    (
        FT_SUSPENSION,
        ("suspended for", "suspended indefinitely", "serving a suspension"),
    ),
    (
        FT_RETIREMENT,
        ("has retired", "announced his retirement", "announced retirement"),
    ),
    (
        FT_INJURY,
        (
            "injured",
            "injury",
            "questionable",
            "doubtful",
            "hamstring",
            "ankle",
            "knee",
            "concussion",
            "surgery",
            "limited practice",
            "did not practice",
            "season-ending",
            "torn acl",
        ),
    ),
)

_SEVERITY_RANK = {
    SEV_NONE: 0,
    SEV_LOW: 1,
    SEV_MEDIUM: 2,
    SEV_HIGH: 3,
    SEV_CRITICAL: 4,
}

_EVENT_BASE_SEVERITY = {
    FT_IR_PUP_NFI: SEV_HIGH,
    FT_INACTIVE: SEV_HIGH,
    FT_INJURY: SEV_MEDIUM,
    FT_INJURY_SEVERITY_UPDATE: SEV_HIGH,
    FT_RETURN_TO_PLAY: SEV_MEDIUM,
    FT_RETURN_TO_PRACTICE: SEV_LOW,
    FT_ACTIVE: SEV_LOW,
    FT_STARTER_CHANGE: SEV_HIGH,
    FT_ROLE_INCREASE: SEV_MEDIUM,
    FT_ROLE_DECREASE: SEV_MEDIUM,
    FT_POSITION_BATTLE: SEV_MEDIUM,
    FT_DEPTH_CHART_CHANGE: SEV_LOW,
    FT_TRADE: SEV_HIGH,
    FT_SIGNING: SEV_MEDIUM,
    FT_RELEASE: SEV_MEDIUM,
    FT_SUSPENSION: SEV_HIGH,
    FT_RETIREMENT: SEV_HIGH,
    FT_OTHER: SEV_NONE,
}

_SPECULATION_STARTER_PHRASES = (
    "could start",
    "might start",
    "expected to start",
    "believed to start",
    "in line to start",
    "candidate to start",
)

_SIGNIFICANT_INJURY_EVENT_PHRASES = (
    "helped off field",
    "helped off the field",
    "carted off",
    "could not put weight on",
    "couldn't put weight on",
    "taken to the locker room",
    "taken to locker room",
    "left practice with injury",
    "left practice with an injury",
    "ruled out",
)


@dataclass(frozen=True)
class FootballEvent:
    """Deterministic football event derived from an article or structured card."""

    event_type: str
    player_name: str = ""
    player_id: str = ""
    team: str = ""
    event_direction: str = ""  # up / down / neutral
    event_time: float = 0.0
    article_time: float = 0.0
    source: str = ""
    source_url: str = ""
    confidence: str = news_signal.CONFIDENCE_SPECULATION
    confirmation_level: str = EVIDENCE_SPECULATION
    event_identity: str = ""
    matched_evidence: tuple[str, ...] = ()
    structured_state_corroboration: bool = False
    roster_relationship: str = REL_UNKNOWN
    explanation: str = ""
    speculative: bool = True
    article_title: str = ""
    signal_primary_event: str = ""
    confirmed_starter: bool = False  # True only for official starter language
    corroboration_label: str = "NEWS ONLY"
    corroboration_note: str = ""
    freshness_bucket: str = ""
    timestamp_source: str = ""
    age_seconds: int = -1
    significant_injury_event: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NewsAlert:
    event: FootballEvent
    severity: str
    should_alert: bool
    title: str
    body: str
    why_care: str
    action_hint: str
    league_relevance_note: str = ""
    escalated_from: str = ""
    suppressed_reason: str = ""

    def as_tile(self) -> Dict[str, Any]:
        family = event_family_key(self.event.event_type)
        stable_id = (
            f"news-event:{self.event.player_id or self.event.player_name or 'unknown'}:{family}"
        )
        note = self.why_care or self.event.corroboration_note or self.body
        return {
            "label": "News Alert",
            "value": self.title,
            "note": note[:160],
            "tone": "risk" if self.severity in {SEV_CRITICAL, SEV_HIGH} else "opportunity",
            "route_key": "alerts" if self.event.roster_relationship == REL_FREE_AGENT else "my_team",
            "route_player_id": self.event.player_id,
            "player_id": self.event.player_id,
            "news_player_name": self.event.player_name,
            "recommendation_id": stable_id,
            "news_event_type": self.event.event_type,
            "news_event_severity": self.severity,
            "news_roster_relationship": self.event.roster_relationship,
            "news_confidence": self.event.confidence,
            "news_confirmation_level": self.event.confirmation_level,
            "news_speculative": self.event.speculative,
            "news_confirmed_starter": self.event.confirmed_starter,
            "news_significant_injury_event": self.event.significant_injury_event,
            "news_why_care": self.why_care,
            "news_action_hint": self.action_hint,
            "news_league_relevance": self.league_relevance_note,
            "news_corroboration": self.event.corroboration_label,
            "news_corroboration_note": self.event.corroboration_note,
            "news_freshness_bucket": self.event.freshness_bucket,
            "news_timestamp_source": self.event.timestamp_source,
            "news_event_time": self.event.event_time,
            "news_source": self.event.source,
            "source_url": self.event.source_url,
            "news_article_title": self.event.article_title,
            "news_age_seconds": self.event.age_seconds,
            "news_age_label": (
                signal_freshness.format_human_age_label(
                    self.event.age_seconds,
                    stale=str(self.event.freshness_bucket).upper() == "STALE",
                )
                if self.event.age_seconds >= 0
                else ""
            ),
            "news_escalated_from": self.escalated_from,
            "should_alert": self.should_alert,
            "valuation_impact": "none_from_article",
            "source_headline": self.title,
            "fantasygm_read": self.why_care,
        }


def classify_fine_grained_event(text: str) -> tuple[str, tuple[str, ...], bool]:
    """Return (event_type, matched_phrases, confirmed_starter).

    Speculation language never yields confirmed_starter=True.
    """

    lower = str(text or "").lower()
    matched: List[str] = []
    event_type = FT_OTHER
    for candidate, phrases in _EVENT_PHRASES:
        hits = [p for p in phrases if news_signal.contains_phrase(lower, p)]
        if hits:
            event_type = candidate
            matched = hits
            break

    speculative_starter = any(news_signal.contains_phrase(lower, p) for p in _SPECULATION_STARTER_PHRASES)
    # Non-contiguous "could … start" / "might … start" still counts as speculation.
    if not speculative_starter and re.search(
        r"\b(could|might|may|expected to|believed to)\b.{0,40}\bstart(?:ing|er)?\b",
        lower,
    ):
        speculative_starter = True
        matched = matched or ("speculative_start_language",)

    if speculative_starter and event_type in {FT_OTHER, FT_POSITION_BATTLE, FT_ROLE_INCREASE}:
        event_type = FT_POSITION_BATTLE
        matched = matched or [p for p in _SPECULATION_STARTER_PHRASES if news_signal.contains_phrase(lower, p)]

    # Questionable → Doubtful / Out phrasing for severity-chain tests.
    if event_type == FT_INJURY and any(
        news_signal.contains_phrase(lower, p)
        for p in ("upgraded to doubtful", "now doubtful", "downgraded to out", "now ruled out", "elevated to out")
    ):
        event_type = FT_INJURY_SEVERITY_UPDATE

    confirmed_starter = False
    if event_type == FT_STARTER_CHANGE:
        # Official starter phrases only — speculative "could start" is not confirmation.
        if speculative_starter and not any(
            news_signal.contains_phrase(lower, p)
            for p in (
                "named the starter",
                "named starter",
                "officially named starter",
                "listed as the starter",
                "listed as starter",
                "has been named the starter",
            )
        ):
            event_type = FT_POSITION_BATTLE
            confirmed_starter = False
        else:
            confirmed_starter = True
    return event_type, tuple(matched), confirmed_starter


def is_significant_injury_event(text: str) -> bool:
    """Recognize high-attention injury events without inferring a diagnosis."""

    lower = str(text or "").lower()
    return any(news_signal.contains_phrase(lower, phrase) for phrase in _SIGNIFICANT_INJURY_EVENT_PHRASES)


def _confirmation_level(confidence: str, *, structured: bool, speculative: bool) -> str:
    if structured:
        return EVIDENCE_STRUCTURED
    if speculative or confidence == news_signal.CONFIDENCE_SPECULATION:
        return EVIDENCE_SPECULATION
    if confidence in {news_signal.CONFIDENCE_OFFICIAL, news_signal.CONFIDENCE_STRONG}:
        return EVIDENCE_CONFIRMED
    if confidence == news_signal.CONFIDENCE_COACH:
        return EVIDENCE_BEAT
    return EVIDENCE_BEAT


def _event_direction(event_type: str) -> str:
    if event_type in {FT_ROLE_INCREASE, FT_STARTER_CHANGE, FT_RETURN_TO_PLAY, FT_RETURN_TO_PRACTICE, FT_ACTIVE, FT_SIGNING}:
        return "up"
    if event_type in {FT_ROLE_DECREASE, FT_INJURY, FT_IR_PUP_NFI, FT_INACTIVE, FT_RELEASE, FT_SUSPENSION, FT_RETIREMENT}:
        return "down"
    return "neutral"


def football_event_from_article(
    item: Mapping[str, Any],
    *,
    structured_corroboration: bool = False,
) -> FootballEvent:
    """Build a FootballEvent from an enriched article dict."""

    enriched = news_signal.enrich_news_item(item) if "signal_primary_event" not in item else dict(item)
    text = news_signal.article_text(enriched)
    event_type, evidence, confirmed_starter = classify_fine_grained_event(text)
    confidence = str(enriched.get("signal_confidence") or news_signal.CONFIDENCE_SPECULATION)
    speculative = bool(enriched.get("signal_speculative")) or confidence == news_signal.CONFIDENCE_SPECULATION
    if confirmed_starter and speculative:
        # Speculative articles cannot confirm starters.
        confirmed_starter = False
        if event_type == FT_STARTER_CHANGE:
            event_type = FT_POSITION_BATTLE
    try:
        article_time = float(enriched.get("published_ts") or 0.0)
    except Exception:
        article_time = 0.0
    from modules import signal_freshness

    fresh = signal_freshness.normalize_news_freshness(enriched)
    identity = str(enriched.get("event_identity") or news_signal.event_identity(enriched))
    family = event_family_key(event_type)
    identity = hashlib.sha1(f"{identity}|{family}".encode("utf-8")).hexdigest()
    explanation = (
        f"{event_type.replace('_', ' ').title()}: "
        f"{str(enriched.get('title') or '')[:140]} "
        f"[{confidence}; {'speculative' if speculative else 'non-speculative'}]"
    )
    return FootballEvent(
        event_type=event_type,
        player_name=str(enriched.get("matched_player") or ""),
        player_id=str(enriched.get("matched_player_id") or enriched.get("player_id") or ""),
        team=str(enriched.get("matched_team") or enriched.get("team") or ""),
        event_direction=_event_direction(event_type),
        event_time=article_time,
        article_time=article_time,
        source=str(enriched.get("source") or ""),
        source_url=str(enriched.get("link") or ""),
        confidence=confidence,
        confirmation_level=_confirmation_level(
            confidence, structured=structured_corroboration, speculative=speculative
        ),
        event_identity=identity,
        matched_evidence=evidence,
        structured_state_corroboration=bool(structured_corroboration),
        explanation=explanation.strip(),
        speculative=speculative,
        article_title=str(enriched.get("title") or ""),
        signal_primary_event=str(enriched.get("signal_primary_event") or ""),
        confirmed_starter=confirmed_starter,
        freshness_bucket=str(fresh.get("freshness_bucket") or ""),
        timestamp_source=str(fresh.get("timestamp_source") or ""),
        age_seconds=int(fresh.get("age_seconds") if fresh.get("age_seconds") is not None else -1),
        significant_injury_event=(
            event_type in {FT_INJURY, FT_INACTIVE, FT_INJURY_SEVERITY_UPDATE}
            and is_significant_injury_event(text)
        ),
    )


def resolve_roster_relationship(
    *,
    player_id: str = "",
    player_name: str = "",
    my_roster_ids: Iterable[str] | None = None,
    my_starter_ids: Iterable[str] | None = None,
    my_taxi_ids: Iterable[str] | None = None,
    my_ir_ids: Iterable[str] | None = None,
    opponent_ids: Iterable[str] | None = None,
    free_agent_ids: Iterable[str] | None = None,
    roster_name_to_id: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Return (relationship, resolved_player_id)."""

    pid = str(player_id or "").strip()
    if not pid and player_name and roster_name_to_id:
        pid = str(roster_name_to_id.get(news_signal.normalize_player_name(player_name)) or "").strip()

    starters = {str(x) for x in (my_starter_ids or []) if x is not None}
    mine = {str(x) for x in (my_roster_ids or []) if x is not None}
    taxi = {str(x) for x in (my_taxi_ids or []) if x is not None}
    ir = {str(x) for x in (my_ir_ids or []) if x is not None}
    opponents = {str(x) for x in (opponent_ids or []) if x is not None}
    fas = {str(x) for x in (free_agent_ids or []) if x is not None}

    if not pid:
        return REL_UNKNOWN, ""
    if pid in starters:
        return REL_MY_STARTER, pid
    if pid in ir:
        return REL_MY_IR, pid
    if pid in taxi:
        return REL_MY_TAXI, pid
    if pid in mine:
        return REL_MY_BENCH, pid
    if pid in fas:
        return REL_FREE_AGENT, pid
    if pid in opponents:
        return REL_OPPONENT_ROSTER, pid
    return REL_UNKNOWN, pid


def resolve_article_player_identity(
    item: Mapping[str, Any],
    *,
    player_name_to_id: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve one article to one canonical player, failing closed on ambiguity."""

    explicit_id = str(item.get("matched_player_id") or item.get("player_id") or "").strip()
    explicit_name = str(item.get("matched_player") or "").strip()
    index = dict(player_name_to_id or {})
    if explicit_id:
        return explicit_name, explicit_id
    if explicit_name:
        resolved = str(index.get(news_signal.normalize_player_name(explicit_name)) or "").strip()
        return explicit_name, resolved
    if not index:
        return "", ""

    text = news_signal.article_text(item)
    matches: list[tuple[str, str]] = []
    for normalized_name, player_id in index.items():
        normalized = str(normalized_name or "").strip()
        pid = str(player_id or "").strip()
        if normalized and pid and news_signal.contains_phrase(text, normalized):
            matches.append((normalized, pid))
    unique_ids = {pid for _, pid in matches}
    if len(unique_ids) != 1:
        return "", ""
    normalized, pid = matches[0]
    return normalized.title(), pid


def contextual_news_alert_from_article(
    item: Mapping[str, Any],
    *,
    my_roster_ids: Iterable[str] | None = None,
    my_starter_ids: Iterable[str] | None = None,
    my_taxi_ids: Iterable[str] | None = None,
    my_ir_ids: Iterable[str] | None = None,
    opponent_ids: Iterable[str] | None = None,
    free_agent_ids: Iterable[str] | None = None,
    player_name_to_id: Mapping[str, str] | None = None,
    players_df: pd.DataFrame | None = None,
    league_settings: Mapping[str, Any] | None = None,
) -> NewsAlert:
    """Build the canonical roster-aware alert used by Dashboard and Alerts."""

    player_name, player_id = resolve_article_player_identity(
        item, player_name_to_id=player_name_to_id
    )
    if player_id and players_df is not None and not getattr(players_df, "empty", True):
        if "player_id" in players_df.columns and "name" in players_df.columns:
            rows = players_df[players_df["player_id"].astype(str) == player_id]
            if not rows.empty:
                player_name = str(rows.iloc[0].get("name") or player_name).strip()
    enriched = dict(item)
    if player_name:
        enriched["matched_player"] = player_name
    if player_id:
        enriched["matched_player_id"] = player_id
    event = football_event_from_article(enriched)
    relationship, resolved_id = resolve_roster_relationship(
        player_id=event.player_id,
        player_name=event.player_name,
        my_roster_ids=my_roster_ids,
        my_starter_ids=my_starter_ids,
        my_taxi_ids=my_taxi_ids,
        my_ir_ids=my_ir_ids,
        opponent_ids=opponent_ids,
        free_agent_ids=free_agent_ids,
        roster_name_to_id=player_name_to_id,
    )
    event = FootballEvent(
        **{
            **event.as_dict(),
            "roster_relationship": relationship,
            "player_id": resolved_id or event.player_id,
            "player_name": player_name or event.player_name,
        }
    )
    event = corroborate_with_structured_injury(event, players_df)
    alert = build_news_alert(event, league_settings=league_settings)
    from modules import alert_presentation

    return alert_presentation.apply_presentation(alert, players_df=players_df)


def _bump_severity(level: str, steps: int = 1) -> str:
    order = [SEV_NONE, SEV_LOW, SEV_MEDIUM, SEV_HIGH, SEV_CRITICAL]
    idx = order.index(level) if level in order else 0
    return order[min(len(order) - 1, idx + steps)]


def compute_alert_severity(
    event: FootballEvent,
    *,
    league_settings: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Return (severity, league_relevance_note). League settings alter relevance only."""

    settings = dict(league_settings or {})
    base = _EVENT_BASE_SEVERITY.get(event.event_type, SEV_NONE)
    note_parts: List[str] = []

    if event.speculative and event.confirmation_level == EVIDENCE_SPECULATION:
        # Speculation never reaches CRITICAL from articles alone.
        if _SEVERITY_RANK[base] > _SEVERITY_RANK[SEV_MEDIUM]:
            base = SEV_MEDIUM
        note_parts.append("speculative confidence")

    rel = event.roster_relationship
    if rel == REL_MY_STARTER:
        base = _bump_severity(base, 1 if base != SEV_CRITICAL else 0)
        if event.event_type in {FT_INACTIVE, FT_IR_PUP_NFI, FT_INJURY} and not event.speculative:
            base = SEV_CRITICAL
        note_parts.append("affects your starter")
    elif rel == REL_MY_BENCH:
        if event.significant_injury_event:
            base = max(base, SEV_HIGH, key=lambda s: _SEVERITY_RANK[s])
            note_parts.append("potentially significant injury event")
        elif event.event_type in {FT_STARTER_CHANGE, FT_ROLE_INCREASE, FT_IR_PUP_NFI} and not event.speculative:
            base = max(base, SEV_HIGH, key=lambda s: _SEVERITY_RANK[s])
        note_parts.append("affects your bench")
    elif rel == REL_MY_TAXI:
        note_parts.append("taxi squad asset")
    elif rel == REL_MY_IR:
        if event.event_type in {FT_RETURN_TO_PLAY, FT_RETURN_TO_PRACTICE, FT_ACTIVE}:
            base = max(base, SEV_HIGH, key=lambda s: _SEVERITY_RANK[s])
        note_parts.append("your IR player")
    elif rel == REL_FREE_AGENT:
        if event.event_type in {FT_STARTER_CHANGE, FT_ROLE_INCREASE} and not event.speculative:
            base = max(base, SEV_HIGH, key=lambda s: _SEVERITY_RANK[s])
            note_parts.append("waiver opportunity")
        elif event.event_type == FT_POSITION_BATTLE:
            base = SEV_LOW
            note_parts.append("watchlist only")
        else:
            if _SEVERITY_RANK[base] >= _SEVERITY_RANK[SEV_HIGH]:
                base = SEV_MEDIUM
            note_parts.append("free agent")
    elif rel == REL_OPPONENT_ROSTER:
        if _SEVERITY_RANK[base] > _SEVERITY_RANK[SEV_MEDIUM]:
            base = SEV_MEDIUM
        note_parts.append("opponent roster")
    else:
        if _SEVERITY_RANK[base] >= _SEVERITY_RANK[SEV_MEDIUM]:
            base = SEV_LOW
        note_parts.append("roster relationship unknown")

    # League-context relevance (never valuation). Apply before early return so
    # dynasty/redraft/SF/TEP notes always attach when relevant.
    qb_format = str(settings.get("qb_format") or "1QB")
    scoring = str(settings.get("scoring_format") or "PPR")
    league_format = str(settings.get("league_format") or "Dynasty")
    te_premium = bool(settings.get("te_premium"))
    blob = f"{event.article_title} {event.explanation}".lower()

    if event.event_type in {FT_STARTER_CHANGE, FT_ROLE_INCREASE, FT_POSITION_BATTLE}:
        if "qb" in blob or "quarterback" in blob:
            if qb_format in {"Superflex", "2QB"}:
                base = _bump_severity(base)
                note_parts.append(f"{qb_format} raises QB alert relevance")
        if te_premium and (" te " in f" {blob} " or "tight end" in blob):
            base = _bump_severity(base)
            note_parts.append("TE premium raises TE role relevance")
        if scoring == "PPR" and ("wr" in blob or "receiver" in blob or "target" in blob):
            note_parts.append("PPR: receiving-role news is more actionable")
        if league_format == "Dynasty" and event.event_direction == "up":
            note_parts.append("dynasty: role upside more actionable")

    if league_format == "Redraft" and event.event_type in {
        FT_INACTIVE,
        FT_IR_PUP_NFI,
        FT_INJURY,
        FT_INJURY_SEVERITY_UPDATE,
    }:
        base = _bump_severity(base)
        note_parts.append("redraft: short-term availability more urgent")

    if base == SEV_NONE or (rel == REL_UNKNOWN and event.speculative):
        return SEV_NONE, "; ".join(note_parts)
    return base, "; ".join(note_parts)


def should_emit_alert(severity: str, event: FootballEvent) -> bool:
    if not event.player_id and event.roster_relationship in {REL_UNKNOWN, REL_FREE_AGENT}:
        if severity not in {SEV_CRITICAL}:
            return False
    if severity in {SEV_NONE, SEV_LOW} and event.roster_relationship in {REL_UNKNOWN, REL_OPPONENT_ROSTER}:
        return False
    if severity == SEV_NONE:
        return False
    if event.event_type == FT_OTHER:
        return False
    if event.speculative and event.roster_relationship in {REL_FREE_AGENT, REL_UNKNOWN} and severity == SEV_LOW:
        return False
    if event.roster_relationship == REL_OPPONENT_ROSTER and severity == SEV_LOW:
        return False
    return True


def _alert_identity_title(event: FootballEvent) -> str:
    who = str(event.player_name or "").strip()
    what = str(event.event_type or "").replace("_", " ").strip()
    what_key = what.casefold()
    if not who or who.casefold() in {"player", "other"}:
        if not str(event.player_id or "").strip():
            if event.roster_relationship in {REL_UNKNOWN, ""}:
                return "League-wide news"
            return "Unmapped player update"
        return "Player mapping unavailable"
    article = str(event.article_title or "").strip()
    if event.event_type == FT_TRADE and who:
        dest = str(event.team or "").strip()
        if dest:
            return f"{who} traded to {dest}"
        return article[:140] if article else f"{who} traded"
    if article:
        return article[:140]
    if what_key in {"", "other"}:
        return "Unmapped player update" if who.casefold() in {"player", "other"} else who
    return f"{who}: {what.title()}"


def _alert_copy(event: FootballEvent, severity: str, league_note: str) -> tuple[str, str, str, str]:
    who = event.player_name or "Player"
    what = event.event_type.replace("_", " ").title()
    title = _alert_identity_title(event)
    certainty = "Speculative" if event.speculative else event.confidence.replace("_", " ")
    event_context = (
        "Potentially significant injury event. Status not yet confirmed. "
        if event.significant_injury_event and not event.structured_state_corroboration
        else ""
    )
    body = (
        f"{event.article_title[:160] or what}. "
        f"{event_context}"
        f"Affects: {event.roster_relationship.replace('_', ' ')}. "
        f"Certainty: {certainty}."
    )
    why = league_note or f"{event.roster_relationship} · {event.confirmation_level}"
    if event.roster_relationship == REL_MY_STARTER and event.event_direction == "down":
        action = "Check lineup / IR / handcuff waivers."
    elif event.roster_relationship == REL_FREE_AGENT and event.event_direction == "up":
        action = "Open Waivers — possible priority add."
    elif event.event_type == FT_POSITION_BATTLE:
        action = "Monitor — not a confirmed starter change."
    elif event.roster_relationship == REL_OPPONENT_ROSTER:
        action = "Useful matchup intel; lower urgency than your roster."
    else:
        action = "Review News / My Team for context."
    return title, body, why, action


def build_news_alert(
    event: FootballEvent,
    *,
    league_settings: Mapping[str, Any] | None = None,
) -> NewsAlert:
    severity, league_note = compute_alert_severity(event, league_settings=league_settings)
    emit = should_emit_alert(severity, event)
    title, body, why, action = _alert_copy(event, severity, league_note)
    return NewsAlert(
        event=event,
        severity=severity,
        should_alert=emit,
        title=title,
        body=body,
        why_care=why,
        action_hint=action,
        league_relevance_note=league_note,
        suppressed_reason="" if emit else "below alert threshold",
    )


def _state_bucket(session: MutableMapping[str, Any], league_id: str) -> Dict[str, Any]:
    root = session.setdefault(ALERT_STATE_KEY, {})
    if not isinstance(root, dict):
        root = {}
        session[ALERT_STATE_KEY] = root
    bucket = root.setdefault(str(league_id or "_"), {"events": {}})
    if not isinstance(bucket, dict):
        bucket = {"events": {}}
        root[str(league_id or "_")] = bucket
    bucket.setdefault("events", {})
    return bucket


def apply_dedupe_and_escalation(
    alert: NewsAlert,
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    now: float | None = None,
    presentation: bool = False,
) -> NewsAlert:
    """Suppress identical repeats; allow severity/confidence escalations.

    ``presentation=True`` keeps cooldown-stable alerts visible for Dashboard /
    package-HIT refresh without treating them as a new notification write.
    """

    if not alert.should_alert:
        return alert
    now_ts = float(now if now is not None else time.time())
    bucket = _state_bucket(session, league_id)
    events: Dict[str, Any] = bucket["events"]
    # Soft identity: player + coarse family for escalation chain.
    family = alert.event.event_type
    family_key = event_family_key(family)
    key = f"{alert.event.player_id or alert.event.player_name}|{family_key}"
    prev = events.get(key) or {}
    prev_sev = str(prev.get("severity") or SEV_NONE)
    prev_conf = str(prev.get("confidence") or "")
    prev_type = str(prev.get("event_type") or "")
    prev_ts = float(prev.get("ts") or 0.0)
    prev_identity = str(prev.get("event_identity") or "")

    # Exact same event identity within cooldown → suppress notification spam.
    if prev_identity == alert.event.event_identity and (now_ts - prev_ts) < ALERT_COOLDOWN_SECONDS:
        if presentation:
            return alert
        return NewsAlert(
            event=alert.event,
            severity=alert.severity,
            should_alert=False,
            title=alert.title,
            body=alert.body,
            why_care=alert.why_care,
            action_hint=alert.action_hint,
            league_relevance_note=alert.league_relevance_note,
            suppressed_reason="duplicate_event_identity_cooldown",
        )

    # Same severity + type within cooldown → suppress spam (e.g. limited practice ×5).
    if (
        prev_type == alert.event.event_type
        and prev_sev == alert.severity
        and prev_conf == alert.event.confidence
        and (now_ts - prev_ts) < ALERT_COOLDOWN_SECONDS
    ):
        if presentation:
            return alert
        return NewsAlert(
            event=alert.event,
            severity=alert.severity,
            should_alert=False,
            title=alert.title,
            body=alert.body,
            why_care=alert.why_care,
            action_hint=alert.action_hint,
            league_relevance_note=alert.league_relevance_note,
            suppressed_reason="repeat_same_severity_cooldown",
        )

    escalated_from = ""
    if _SEVERITY_RANK.get(alert.severity, 0) > _SEVERITY_RANK.get(prev_sev, 0) and prev_ts > 0:
        escalated_from = prev_sev
    if prev_type == FT_POSITION_BATTLE and alert.event.event_type == FT_STARTER_CHANGE:
        escalated_from = escalated_from or prev_type
    if (
        prev_ts > 0
        and prev_type
        and prev_type != alert.event.event_type
        and event_family_key(prev_type) == family_key
    ):
        escalated_from = escalated_from or prev_type

    events[key] = {
        "severity": alert.severity,
        "confidence": alert.event.confidence,
        "event_type": alert.event.event_type,
        "event_identity": alert.event.event_identity,
        "ts": now_ts,
    }
    # Bound memory.
    if len(events) > 200:
        oldest = sorted(events.items(), key=lambda kv: float((kv[1] or {}).get("ts") or 0))[:50]
        for drop_key, _ in oldest:
            events.pop(drop_key, None)

    return NewsAlert(
        event=alert.event,
        severity=alert.severity,
        should_alert=True,
        title=alert.title,
        body=alert.body,
        why_care=alert.why_care,
        action_hint=alert.action_hint,
        league_relevance_note=alert.league_relevance_note,
        escalated_from=escalated_from,
    )


def clear_alert_state(session: MutableMapping[str, Any], *, league_id: str | None = None) -> None:
    root = session.get(ALERT_STATE_KEY)
    if not isinstance(root, dict):
        session.pop(ALERT_STATE_KEY, None)
    elif league_id is None:
        session.pop(ALERT_STATE_KEY, None)
    else:
        root.pop(str(league_id), None)
    clear_news_presentation_state(session, league_id=str(league_id or ""))


def _name_index(df: pd.DataFrame) -> Dict[str, str]:
    if df is None or getattr(df, "empty", True):
        return {}
    mapping: Dict[str, str] = {}
    ambiguous: set[str] = set()
    if "name" not in df.columns or "player_id" not in df.columns:
        return mapping
    for _, row in df.iterrows():
        key = news_signal.normalize_player_name(str(row.get("name") or ""))
        pid = str(row.get("player_id") or "")
        if key and pid:
            prior = mapping.get(key)
            if prior and prior != pid:
                ambiguous.add(key)
            else:
                mapping[key] = pid
    for key in ambiguous:
        mapping.pop(key, None)
    return mapping


def canonical_player_name_index(df: pd.DataFrame | None) -> Dict[str, str]:
    """Return the ambiguity-safe canonical name → player-id resolver."""

    return _name_index(df) if df is not None else {}


def corroborate_with_structured_injury(
    event: FootballEvent,
    players_df: pd.DataFrame | None,
) -> FootballEvent:
    """Mark structured corroboration when Sleeper injury/status already matches."""

    from modules import signal_corroboration

    status = ""
    injury = ""
    if players_df is not None and not getattr(players_df, "empty", True) and event.player_id:
        if "player_id" in players_df.columns:
            rows = players_df[players_df["player_id"].astype(str) == str(event.player_id)]
            if not rows.empty:
                row = rows.iloc[0]
                status = str(row.get("status") or "")
                injury = str(row.get("injury_status") or "")
    result = signal_corroboration.corroborate_news_with_status(
        event,
        sleeper_status=status,
        injury_status=injury,
        player_id=event.player_id,
    )
    label = str(result.get("label") or signal_corroboration.LABEL_NEWS_ONLY)
    corroborated = label == signal_corroboration.LABEL_CORROBORATED
    updates = {
        "corroboration_label": label,
        "corroboration_note": str(result.get("note") or ""),
        "structured_state_corroboration": corroborated,
    }
    if corroborated:
        updates["confirmation_level"] = EVIDENCE_STRUCTURED
        updates["speculative"] = False if event.confirmation_level != EVIDENCE_SPECULATION else event.speculative
    return FootballEvent(**{**event.as_dict(), **updates})


def build_roster_news_alert_tiles(
    articles: Sequence[Mapping[str, Any]],
    *,
    session: MutableMapping[str, Any],
    league_id: str,
    league_settings: Mapping[str, Any] | None = None,
    my_team_df: pd.DataFrame | None = None,
    starters_df: pd.DataFrame | None = None,
    free_agents_df: pd.DataFrame | None = None,
    opponent_ids: Iterable[str] | None = None,
    taxi_ids: Iterable[str] | None = None,
    ir_ids: Iterable[str] | None = None,
    players_df: pd.DataFrame | None = None,
    now: float | None = None,
    max_tiles: int = MAX_NEWS_ALERT_TILES,
    presentation: bool = False,
) -> List[Dict[str, Any]]:
    """Build Dashboard tiles from cached articles. Fail-soft; never fetches."""

    try:
        return _build_roster_news_alert_tiles_unsafe(
            articles,
            session=session,
            league_id=league_id,
            league_settings=league_settings,
            my_team_df=my_team_df,
            starters_df=starters_df,
            free_agents_df=free_agents_df,
            opponent_ids=opponent_ids,
            taxi_ids=taxi_ids,
            ir_ids=ir_ids,
            players_df=players_df,
            now=now,
            max_tiles=max_tiles,
            presentation=presentation,
        )
    except Exception:
        return []


def _build_roster_news_alert_tiles_unsafe(
    articles: Sequence[Mapping[str, Any]],
    *,
    session: MutableMapping[str, Any],
    league_id: str,
    league_settings: Mapping[str, Any] | None,
    my_team_df: pd.DataFrame | None,
    starters_df: pd.DataFrame | None,
    free_agents_df: pd.DataFrame | None,
    opponent_ids: Iterable[str] | None,
    taxi_ids: Iterable[str] | None,
    ir_ids: Iterable[str] | None,
    players_df: pd.DataFrame | None,
    now: float | None,
    max_tiles: int,
    presentation: bool = False,
) -> List[Dict[str, Any]]:
    my_ids = []
    if my_team_df is not None and not my_team_df.empty and "player_id" in my_team_df.columns:
        my_ids = [str(x) for x in my_team_df["player_id"].tolist()]
    starter_ids = []
    if starters_df is not None and not starters_df.empty and "player_id" in starters_df.columns:
        if "suggested_starter" in starters_df.columns:
            starter_ids = [
                str(x)
                for x in starters_df.loc[starters_df["suggested_starter"].fillna(False), "player_id"].tolist()
            ]
        else:
            starter_ids = [str(x) for x in starters_df["player_id"].tolist()]
    fa_ids = []
    if free_agents_df is not None and not free_agents_df.empty and "player_id" in free_agents_df.columns:
        fa_ids = [str(x) for x in free_agents_df["player_id"].tolist()]

    name_maps = [
        _name_index(my_team_df) if my_team_df is not None else {},
        _name_index(free_agents_df) if free_agents_df is not None else {},
        _name_index(players_df) if players_df is not None else {},
    ]
    name_to_id: Dict[str, str] = {}
    ambiguous_names: set[str] = set()
    for mapping in name_maps:
        for name, player_id in mapping.items():
            prior = name_to_id.get(name)
            if prior and prior != player_id:
                ambiguous_names.add(name)
            else:
                name_to_id[name] = player_id
    for name in ambiguous_names:
        name_to_id.pop(name, None)

    alerts: List[NewsAlert] = []
    timeline_alerts: List[NewsAlert] = []
    for raw in articles or []:
        if not isinstance(raw, Mapping):
            continue
        alert = contextual_news_alert_from_article(
            raw,
            my_roster_ids=my_ids,
            my_starter_ids=starter_ids,
            my_taxi_ids=taxi_ids,
            my_ir_ids=ir_ids,
            opponent_ids=opponent_ids,
            free_agent_ids=fa_ids,
            player_name_to_id=name_to_id,
            players_df=players_df if players_df is not None else my_team_df,
            league_settings=league_settings,
        )
        alert = apply_dedupe_and_escalation(
            alert,
            session,
            league_id=league_id,
            now=now,
            presentation=presentation,
        )
        timeline_alerts.append(alert)
        if alert.should_alert:
            alerts.append(alert)

    alerts.sort(key=lambda a: (_SEVERITY_RANK.get(a.severity, 0), a.event.article_time), reverse=True)
    # One tile per evolving event family (Q → OUT stays one alert).
    deduped: List[NewsAlert] = []
    seen_ids: set[str] = set()
    for alert in alerts:
        tile_id = f"{alert.event.player_id or alert.event.player_name}:{event_family_key(alert.event.event_type)}"
        if tile_id in seen_ids:
            continue
        seen_ids.add(tile_id)
        deduped.append(alert)
    tiles = [a.as_tile() for a in deduped[: max(0, int(max_tiles))]]
    try:
        from modules import alerts_activity

        timeline_payload = []
        seen_timeline: set[str] = set()
        for alert in sorted(
            timeline_alerts,
            key=lambda a: (_SEVERITY_RANK.get(a.severity, 0), a.event.article_time),
            reverse=True,
        ):
            tile = alert.as_tile()
            key = str(tile.get("recommendation_id") or tile.get("player_id") or "")
            if key in seen_timeline:
                continue
            seen_timeline.add(key)
            timeline_payload.append(tile)
        alerts_activity.store_timeline_events(session, timeline_payload, league_id=league_id)
        session[TIMELINE_EVENT_KEY] = timeline_payload
    except Exception:
        pass
    return tiles


def article_changes_valuation_columns(before: Mapping[str, Any], after: Mapping[str, Any]) -> List[str]:
    """Return valuation columns that changed — must be empty for article-only paths."""

    changed = []
    for col in VALUATION_COLUMNS:
        if before.get(col) != after.get(col):
            changed.append(col)
    return changed


def independent_corroboration_bonus(
    articles: Sequence[Mapping[str, Any]],
    *,
    event_identity_key: str = "event_identity",
) -> Dict[str, int]:
    """Count genuinely independent sources per event_identity.

    Syndication (same title-day identity, different URLs) shares one identity
    from ``news_signal.event_identity`` and therefore does NOT inflate the count.
    Distinct identities for the same player+family still count separately.
    """

    by_id: Dict[str, set[str]] = {}
    for raw in articles or []:
        if not isinstance(raw, Mapping):
            continue
        identity = str(raw.get(event_identity_key) or news_signal.event_identity(raw) or "")
        if not identity:
            continue
        source = str(raw.get("source") or raw.get("link") or "").casefold()
        # Normalize host-ish tokens; aggregators collapse together.
        if "news.google" in source or "google news" in source:
            source_key = "aggregator"
        else:
            source_key = source.split("/")[2] if "://" in source else source
        by_id.setdefault(identity, set()).add(source_key or "unknown")
    return {identity: len(sources) for identity, sources in by_id.items()}


def opponent_ids_from_roster_map(
    roster_player_map: Mapping[Any, Any] | None,
    *,
    my_roster_id: Any,
) -> List[str]:
    """Derive opponent player ids from shared league context — no provider refetch."""

    if not isinstance(roster_player_map, Mapping) or my_roster_id is None:
        return []
    mine = str(my_roster_id)
    out: List[str] = []
    for roster_id, players in roster_player_map.items():
        if str(roster_id) == mine:
            continue
        if not isinstance(players, (list, tuple, set)):
            continue
        for pid in players:
            if pid is not None:
                out.append(str(pid))
    return out


def populate_structured_role_notes_from_sleeper(
    player_row: Mapping[str, Any],
    *,
    previous_depth: str = "",
    previous_order: Any = None,
) -> Dict[str, str]:
    """Populate role/depth notes from structured Sleeper diffs only — never headlines."""

    depth = str(player_row.get("depth_chart_position") or "").strip()
    order = player_row.get("depth_chart_order")
    notes: Dict[str, str] = {}
    if depth and depth != str(previous_depth or "").strip():
        notes["depth_chart_note"] = f"Sleeper depth chart now {depth}."
        notes["role_change_note"] = f"Structured depth changed to {depth}."
    elif order is not None and previous_order is not None and str(order) != str(previous_order):
        notes["depth_chart_note"] = f"Sleeper depth order now {order}."
        notes["role_change_note"] = f"Structured depth order changed to {order}."
    return notes


def _id_list(values: Iterable[Any] | None) -> List[str]:
    out: List[str] = []
    for value in values or ():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out.append(text)
    return out


def store_news_roster_context(
    session: MutableMapping[str, Any],
    *,
    league_id: str,
    roster_id: str = "",
    my_roster_ids: Iterable[Any] | None = None,
    starter_ids: Iterable[Any] | None = None,
    taxi_ids: Iterable[Any] | None = None,
    ir_ids: Iterable[Any] | None = None,
    opponent_ids: Iterable[Any] | None = None,
    free_agent_ids: Iterable[Any] | None = None,
    player_name_to_id: Mapping[str, Any] | None = None,
) -> None:
    """Persist lightweight roster relationship inputs for package-HIT alert refresh."""

    session[ROSTER_CONTEXT_KEY] = {
        "league_id": str(league_id or "").strip(),
        "roster_id": str(roster_id or "").strip(),
        "my_roster_ids": _id_list(my_roster_ids),
        "starter_ids": _id_list(starter_ids),
        "taxi_ids": _id_list(taxi_ids),
        "ir_ids": _id_list(ir_ids),
        "opponent_ids": _id_list(opponent_ids),
        "free_agent_ids": _id_list(free_agent_ids),
        "player_name_to_id": {
            str(name): str(player_id)
            for name, player_id in (player_name_to_id or {}).items()
            if str(name).strip() and str(player_id).strip()
        },
    }
    session.pop(ROSTER_CONTEXT_PENDING_KEY, None)


def load_news_roster_context(
    session: Mapping[str, Any],
    *,
    league_id: str = "",
) -> Dict[str, Any]:
    raw = session.get(ROSTER_CONTEXT_KEY)
    if not isinstance(raw, Mapping):
        return {}
    stored_league = str(raw.get("league_id") or "").strip()
    if league_id and stored_league and stored_league != str(league_id).strip():
        return {}
    return {
        "league_id": stored_league,
        "roster_id": str(raw.get("roster_id") or "").strip(),
        "my_roster_ids": _id_list(raw.get("my_roster_ids")),
        "starter_ids": _id_list(raw.get("starter_ids")),
        "taxi_ids": _id_list(raw.get("taxi_ids")),
        "ir_ids": _id_list(raw.get("ir_ids")),
        "opponent_ids": _id_list(raw.get("opponent_ids")),
        "free_agent_ids": _id_list(raw.get("free_agent_ids")),
        "player_name_to_id": {
            str(name): str(player_id)
            for name, player_id in (
                raw.get("player_name_to_id")
                if isinstance(raw.get("player_name_to_id"), Mapping)
                else {}
            ).items()
            if str(name).strip() and str(player_id).strip()
        },
    }


def clear_news_presentation_state(
    session: MutableMapping[str, Any],
    *,
    league_id: str = "",
) -> None:
    """Drop ephemeral news presentation state (league/account hygiene)."""

    ctx = session.get(ROSTER_CONTEXT_KEY)
    if league_id and isinstance(ctx, Mapping):
        stored = str(ctx.get("league_id") or "").strip()
        if stored and stored != str(league_id).strip():
            session.pop(ROSTER_CONTEXT_KEY, None)
            session.pop(PRESENTATION_DIGEST_KEY, None)
            session.pop(TIMELINE_EVENT_KEY, None)
            return
    session.pop(ROSTER_CONTEXT_KEY, None)
    session.pop(PRESENTATION_DIGEST_KEY, None)
    session.pop(TIMELINE_EVENT_KEY, None)


def presentation_digest_from_tiles(tiles: Sequence[Mapping[str, Any]]) -> str:
    """Deterministic digest of alert-layer fields that affect presentation."""

    rows: List[str] = []
    for tile in tiles or ():
        if not isinstance(tile, Mapping):
            continue
        if str(tile.get("label") or "") != NEWS_ALERT_LABEL:
            continue
        rows.append(
            "|".join(
                (
                    str(tile.get("recommendation_id") or ""),
                    str(tile.get("news_event_type") or ""),
                    str(tile.get("player_id") or tile.get("route_player_id") or ""),
                    str(tile.get("news_confidence") or ""),
                    str(tile.get("news_event_severity") or ""),
                    str(tile.get("news_roster_relationship") or ""),
                    str(tile.get("news_confirmation_level") or ""),
                    str(tile.get("value") or ""),
                    str(tile.get("news_freshness_bucket") or ""),
                    str(tile.get("news_corroboration") or ""),
                )
            )
        )
    payload = "\n".join(sorted(rows))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def actionable_news_digest(
    articles: Sequence[Mapping[str, Any]],
    *,
    session: MutableMapping[str, Any],
    league_id: str,
    league_settings: Mapping[str, Any] | None = None,
    my_team_df: pd.DataFrame | None = None,
    starters_df: pd.DataFrame | None = None,
    free_agents_df: pd.DataFrame | None = None,
    opponent_ids: Iterable[str] | None = None,
    taxi_ids: Iterable[str] | None = None,
    ir_ids: Iterable[str] | None = None,
    players_df: pd.DataFrame | None = None,
    now: float | None = None,
    max_tiles: int = MAX_NEWS_ALERT_TILES,
) -> tuple[str, List[Dict[str, Any]]]:
    """Build news tiles + digest from cached articles (no live fetch)."""

    tiles = build_roster_news_alert_tiles(
        articles,
        session=session,
        league_id=league_id,
        league_settings=league_settings,
        my_team_df=my_team_df,
        starters_df=starters_df,
        free_agents_df=free_agents_df,
        opponent_ids=opponent_ids,
        taxi_ids=taxi_ids,
        ir_ids=ir_ids,
        players_df=players_df,
        now=now,
        max_tiles=max_tiles,
        presentation=True,
    )
    return presentation_digest_from_tiles(tiles), tiles


def _iter_briefing_tiles(dashboard_briefing: Any) -> List[Dict[str, Any]]:
    tiles: List[Dict[str, Any]] = []
    if dashboard_briefing is None:
        return tiles
    primary = getattr(dashboard_briefing, "primary", None)
    if isinstance(primary, Mapping):
        tiles.append(dict(primary))
    for zone in (
        getattr(dashboard_briefing, "immediate", ()) or (),
        getattr(dashboard_briefing, "intelligence", ()) or (),
        getattr(dashboard_briefing, "additional", ()) or (),
    ):
        for item in zone:
            if isinstance(item, Mapping):
                tiles.append(dict(item))
    return tiles


def football_tiles_excluding_news(
    dashboard_briefing: Any,
) -> List[Dict[str, Any]]:
    """Return non-news tiles from a packaged Dashboard briefing."""

    return [
        tile
        for tile in _iter_briefing_tiles(dashboard_briefing)
        if str(tile.get("label") or "") != NEWS_ALERT_LABEL
    ]


def merge_news_tiles_into_dashboard_briefing(
    dashboard_briefing: Any,
    news_tiles: Sequence[Mapping[str, Any]],
):
    """Replace News Alert tiles while preserving football package tiles."""

    from modules import dashboard_workflow

    football_tiles = football_tiles_excluding_news(dashboard_briefing)
    combined = list(football_tiles) + [
        dict(tile) for tile in news_tiles if isinstance(tile, Mapping)
    ]
    prior_immediate = {
        str(item.get("label") or "")
        for item in (getattr(dashboard_briefing, "immediate", ()) or ())
        if isinstance(item, Mapping)
    }
    prior_non_news = frozenset(
        label for label in prior_immediate if label and label != NEWS_ALERT_LABEL
    )
    news_immediate = frozenset(
        {NEWS_ALERT_LABEL}
        if any(
            str(t.get("label") or "") == NEWS_ALERT_LABEL
            and str(t.get("news_event_severity") or "") in {SEV_CRITICAL, SEV_HIGH}
            for t in news_tiles
            if isinstance(t, Mapping)
        )
        else ()
    )
    return dashboard_workflow.organize_dashboard_items(
        combined,
        immediate_labels=prior_non_news.union(news_immediate),
    )


def refresh_news_alerts_for_presentation(
    *,
    session: MutableMapping[str, Any],
    dashboard_briefing: Any,
    articles: Sequence[Mapping[str, Any]],
    league_id: str,
    league_settings: Mapping[str, Any] | None = None,
    my_team_df: pd.DataFrame | None = None,
    now: float | None = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Refresh News Alert tiles on Game Plan package HIT without football rebuild.

    Returns diagnostics + possibly replaced ``dashboard_briefing``.
    """

    started = time.perf_counter()
    stats = session.setdefault(PRESENTATION_STATS_KEY, {})
    if not isinstance(stats, dict):
        stats = {}
        session[PRESENTATION_STATS_KEY] = stats

    ctx = load_news_roster_context(session, league_id=league_id)
    starter_ids = ctx.get("starter_ids") or []
    taxi_ids = ctx.get("taxi_ids") or []
    ir_ids = ctx.get("ir_ids") or []
    opponent_ids = ctx.get("opponent_ids") or []
    free_agent_ids = ctx.get("free_agent_ids") or []

    starters_df = None
    if starter_ids:
        starters_df = pd.DataFrame({"player_id": starter_ids})
    free_agents_df = None
    if free_agent_ids:
        free_agents_df = pd.DataFrame({"player_id": free_agent_ids})

    digest, tiles = actionable_news_digest(
        articles,
        session=session,
        league_id=league_id,
        league_settings=league_settings,
        my_team_df=my_team_df,
        starters_df=starters_df,
        free_agents_df=free_agents_df,
        opponent_ids=opponent_ids,
        taxi_ids=taxi_ids,
        ir_ids=ir_ids,
        players_df=my_team_df,
        now=now,
    )
    previous = str(session.get(PRESENTATION_DIGEST_KEY) or "")
    packaged_digest = presentation_digest_from_tiles(_iter_briefing_tiles(dashboard_briefing))
    # Refresh when cached news presentation diverges from the packaged tiles.
    # Empty previous + matching package means a cold HIT with unchanged news — skip.
    changed = bool(force) or digest != packaged_digest or (
        bool(previous) and digest != previous
    )
    stats["alert_recompute_count"] = int(stats.get("alert_recompute_count") or 0) + 1
    stats["last_digest"] = digest
    stats["last_elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    stats["last_changed"] = bool(changed)
    stats["last_tile_count"] = len(tiles)

    if not changed:
        stats["alert_refresh_skipped"] = int(stats.get("alert_refresh_skipped") or 0) + 1
        return {
            "changed": False,
            "digest": digest,
            "tiles": tiles,
            "dashboard_briefing": dashboard_briefing,
            "elapsed_ms": stats["last_elapsed_ms"],
        }

    merged = merge_news_tiles_into_dashboard_briefing(dashboard_briefing, tiles)
    session[PRESENTATION_DIGEST_KEY] = digest
    stats["alert_refresh_applied"] = int(stats.get("alert_refresh_applied") or 0) + 1
    return {
        "changed": True,
        "digest": digest,
        "tiles": tiles,
        "dashboard_briefing": merged,
        "elapsed_ms": stats["last_elapsed_ms"],
    }
