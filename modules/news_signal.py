"""Canonical news → structured signal classification.

Articles are evidence for presentation, prioritization, and alerts-adjacent
ranking. They must NEVER directly mutate dynasty/value scores. Evaluation
impact arrives only via structured football state (primarily Sleeper status /
injury_status / depth metadata), not headline sentiment.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence

# --- Taxonomies ----------------------------------------------------------------

EVENT_INJURY = "injury/status"
EVENT_ROLE = "role/depth chart"
EVENT_TRANSACTION = "transaction"
EVENT_OFF_FIELD = "off-field/drama"
EVENT_MENTION = "player mention"
EVENT_HEADLINE = "player headline"
EVENT_SLEEPER = "Sleeper status/role metadata changed"

# Compatibility alias used by Google-news path historically.
EVENT_TRANSACTION_DRAMA = "transaction/drama"

CONFIDENCE_OFFICIAL = "official_confirmed"
CONFIDENCE_STRONG = "strong_reporter_confirmation"
CONFIDENCE_COACH = "coach_statement"
CONFIDENCE_OBSERVATION = "credible_observation"
CONFIDENCE_SPECULATION = "speculation"

SOURCE_OFFICIAL = "official"
SOURCE_MAJOR = "major_national"
SOURCE_BEAT = "beat_or_wire"
SOURCE_AGGREGATOR = "aggregator"
SOURCE_OPINION = "opinion_fantasy"
SOURCE_UNKNOWN = "unknown"

# Ranking-only adjustments (never valuation).
SPECULATION_PRIORITY_PENALTY = 40
OFFICIAL_PRIORITY_BONUS = 12
STRONG_PRIORITY_BONUS = 6

NAME_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "v"})

CONTEXT_PHRASES: Dict[str, tuple[str, ...]] = {
    EVENT_INJURY: (
        "injury",
        "injured",
        "questionable",
        "probable",
        "doubtful",
        "unlikely",
        "out",
        "inactive",
        "practice",
        "limited",
        "full participant",
        "did not practice",
        "surgery",
        "injured reserve",
        "ir",
        "pup",
        "nfi",
        "protocol",
        "concussion",
        "hamstring",
        "ankle",
        "knee",
        "illness",
        "return",
        "activated",
        "designated to return",
        "torn acl",
        "acl tear",
        "season-ending",
        "season ending",
    ),
    EVENT_ROLE: (
        "starter",
        "starting",
        "depth chart",
        "first-team",
        "first team",
        "backup",
        "benched",
        "qb1",
        "rb1",
        "wr1",
        "te1",
        "competition",
        "compete",
        "snap",
        "snaps",
        "target",
        "targets",
        "workload",
        "touches",
        "role",
    ),
    EVENT_TRANSACTION: (
        "signed",
        "released",
        "waived",
        "claimed",
        "elevated",
        "practice squad",
        "extension",
        "contract",
        "trade",
        "traded",
        "acquired",
    ),
    EVENT_OFF_FIELD: (
        "holdout",
        "hold-in",
        "unhappy",
        "trade request",
        "suspended",
        "suspension",
        "arrest",
        "charged",
        "domestic",
        "lawsuit",
        "discipline",
        "fine",
        "investigation",
    ),
}

OFFICIAL_CONFIRMATION_PHRASES = (
    "named the starter",
    "named starter",
    "official depth chart",
    "listed as the starter",
    "listed as starter",
    "placed on injured reserve",
    "placed on ir",
    "activated from injured reserve",
    "activated from ir",
    "designated to return",
    "suspended for",
    "released by the",
    "signed by the",
    "traded to the",
)

COACH_STATEMENT_PHRASES = (
    "coach said",
    "coach says",
    "head coach",
    "offensive coordinator said",
    "defensive coordinator said",
)

STRONG_CONFIRMATION_PHRASES = (
    "confirmed",
    "announced",
    "ruled out",
    "ruled him out",
    "will start",
    "is starting",
    "has been named",
)

SPECULATION_PHRASES = (
    "could",
    "may",
    "might",
    "expected to",
    "believed to",
    "rumored",
    "rumour",
    "speculation",
    "speculated",
    "sources say",
    "according to fantasy",
    "breakout season",
    "breakout candidate",
    "could see more work",
    "competing for",
    "in the mix",
    "should get more",
    "fantasy managers",
    "sleeper pick",
    "must-add",
    "must add",
)

OPINION_SOURCE_MARKERS = (
    "fantasypros",
    "fantasy football",
    "dynasty league football",
    "rotoballer",
    "numberfire",
    "fantasy alarm",
)

AGGREGATOR_SOURCE_MARKERS = (
    "news.google",
    "google news",
    "yahoo.com/news",
)

MAJOR_SOURCE_MARKERS = (
    "espn.com",
    "nfl.com",
    "cbssports.com",
    "rotowire.com",
    "theathletic.com",
    "apnews.com",
    "reuters.com",
)

OFFICIAL_SOURCE_MARKERS = (
    "nfl.com/transactions",
    "official",
)


@dataclass(frozen=True)
class NewsSignal:
    """Structured classification for one article. Presentation/ranking only."""

    events: tuple[str, ...]
    primary_event: str
    confidence: str
    source_quality: str
    speculative: bool
    priority_adjustment: int
    relevance_reason: str
    notes: tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def contains_phrase(text: str, phrase: str) -> bool:
    """Word-boundary-safe phrase match (multi-word uses substring)."""

    phrase = str(phrase or "").lower().strip()
    if not phrase:
        return False
    haystack = str(text or "").lower()
    if " " in phrase or "-" in phrase:
        return phrase in haystack
    return re.search(rf"\b{re.escape(phrase)}\b", haystack) is not None


def normalize_player_name(name: str) -> str:
    """Lowercased full name without generational suffixes."""

    tokens = [
        token
        for token in re.findall(r"[a-z0-9']+", str(name or "").lower())
        if token not in NAME_SUFFIXES
    ]
    return " ".join(tokens).strip()


def player_last_name(name: str) -> str:
    normalized = normalize_player_name(name)
    if not normalized:
        return ""
    parts = normalized.split()
    last = parts[-1] if parts else ""
    return last if len(last) >= 4 else ""


def article_text(item: Mapping[str, Any] | None, *extra: str) -> str:
    payload = item or {}
    chunks: List[str] = []
    for key in ("title", "summary", "description", "body", "content"):
        chunks.append(str(payload.get(key) or ""))
    chunks.extend(str(part or "") for part in extra)
    return " ".join(chunks)


def classify_contexts(text: str) -> List[str]:
    matches: List[str] = []
    for label, phrases in CONTEXT_PHRASES.items():
        if any(contains_phrase(text, phrase) for phrase in phrases):
            matches.append(label)
    return matches


def classify_source_quality(source: str | None) -> str:
    blob = str(source or "").casefold()
    if not blob:
        return SOURCE_UNKNOWN
    if any(marker in blob for marker in OFFICIAL_SOURCE_MARKERS):
        return SOURCE_OFFICIAL
    if any(marker in blob for marker in OPINION_SOURCE_MARKERS):
        return SOURCE_OPINION
    if any(marker in blob for marker in AGGREGATOR_SOURCE_MARKERS):
        return SOURCE_AGGREGATOR
    if any(marker in blob for marker in MAJOR_SOURCE_MARKERS):
        return SOURCE_MAJOR
    if "sleeper" in blob:
        return SOURCE_OFFICIAL
    return SOURCE_BEAT if blob else SOURCE_UNKNOWN


def _confidence_from_text(text: str, *, source_quality: str, events: Sequence[str]) -> str:
    lower = str(text or "").lower()
    if any(contains_phrase(lower, phrase) for phrase in OFFICIAL_CONFIRMATION_PHRASES):
        return CONFIDENCE_OFFICIAL
    if source_quality == SOURCE_OFFICIAL and events:
        return CONFIDENCE_OFFICIAL
    if any(contains_phrase(lower, phrase) for phrase in COACH_STATEMENT_PHRASES):
        return CONFIDENCE_COACH
    if any(contains_phrase(lower, phrase) for phrase in STRONG_CONFIRMATION_PHRASES):
        return CONFIDENCE_STRONG
    if any(contains_phrase(lower, phrase) for phrase in SPECULATION_PHRASES):
        return CONFIDENCE_SPECULATION
    if source_quality == SOURCE_OPINION:
        return CONFIDENCE_SPECULATION
    if events:
        return CONFIDENCE_OBSERVATION
    return CONFIDENCE_SPECULATION


def _priority_adjustment(confidence: str, *, speculative: bool) -> int:
    if speculative or confidence == CONFIDENCE_SPECULATION:
        return -SPECULATION_PRIORITY_PENALTY
    if confidence == CONFIDENCE_OFFICIAL:
        return OFFICIAL_PRIORITY_BONUS
    if confidence == CONFIDENCE_STRONG:
        return STRONG_PRIORITY_BONUS
    if confidence == CONFIDENCE_COACH:
        return 2
    return 0


def classify_article(
    text: str,
    *,
    source: str | None = None,
    default_event: str = EVENT_HEADLINE,
) -> NewsSignal:
    """Classify one article into structured signal fields (no valuation)."""

    events = tuple(classify_contexts(text))
    source_quality = classify_source_quality(source)
    confidence = _confidence_from_text(text, source_quality=source_quality, events=events)
    speculative = confidence == CONFIDENCE_SPECULATION or source_quality == SOURCE_OPINION
    if events:
        # Prefer injury > transaction > role > off-field for primary label.
        order = (EVENT_INJURY, EVENT_TRANSACTION, EVENT_ROLE, EVENT_OFF_FIELD)
        primary = next((label for label in order if label in events), events[0])
        relevance_reason = ", ".join(events)
    else:
        primary = default_event
        relevance_reason = default_event
    notes: List[str] = []
    if speculative:
        notes.append("speculative_or_opinion")
    if source_quality == SOURCE_AGGREGATOR:
        notes.append("aggregator_source")
    return NewsSignal(
        events=events,
        primary_event=primary,
        confidence=confidence,
        source_quality=source_quality,
        speculative=speculative,
        priority_adjustment=_priority_adjustment(confidence, speculative=speculative),
        relevance_reason=relevance_reason,
        notes=tuple(notes),
    )


def relevance_reason_for_google_path(text: str) -> str:
    """Preserve legacy Google-news reason labels while fixing substring bugs."""

    signal = classify_article(text, default_event=EVENT_HEADLINE)
    if not signal.events:
        return EVENT_HEADLINE
    # Historical Google path collapsed transaction + off-field.
    labels: List[str] = []
    for event in signal.events:
        if event in {EVENT_TRANSACTION, EVENT_OFF_FIELD}:
            label = EVENT_TRANSACTION_DRAMA
        else:
            label = event
        if label not in labels:
            labels.append(label)
    return ", ".join(labels)


def event_identity(item: Mapping[str, Any]) -> str:
    """Canonical identity for dedupe across syndicated URLs."""

    player = normalize_player_name(str(item.get("matched_player") or ""))
    reason = str(item.get("relevance_reason") or item.get("signal_primary_event") or "").lower()
    title = re.sub(r"[^a-z0-9]+", " ", str(item.get("title") or "").lower()).strip()
    # Bucket by day so updated syndicated copies collide.
    try:
        ts = float(item.get("published_ts") or 0)
    except Exception:
        ts = 0.0
    day = int(ts // 86400) if ts > 0 else 0
    raw = f"{player}|{reason}|{title[:96]}|{day}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def enrich_news_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Attach signal_* metadata. Does not mutate player valuation fields."""

    enriched = dict(item)
    text = article_text(enriched)
    signal = classify_article(text, source=str(enriched.get("source") or ""))
    # Keep existing relevance_reason when already set by matchers; still expose taxonomy.
    if not str(enriched.get("relevance_reason") or "").strip():
        enriched["relevance_reason"] = signal.relevance_reason
    enriched["signal_events"] = list(signal.events)
    enriched["signal_primary_event"] = signal.primary_event
    enriched["signal_confidence"] = signal.confidence
    enriched["signal_source_quality"] = signal.source_quality
    enriched["signal_speculative"] = signal.speculative
    enriched["signal_notes"] = list(signal.notes)
    enriched["signal_priority_adjustment"] = int(signal.priority_adjustment)
    enriched["event_identity"] = event_identity(enriched)
    return enriched


def names_collide(candidate: str, article_text_blob: str, *, roster_names: Sequence[str]) -> bool:
    """True when last-name-only matching would be ambiguous among roster names."""

    last = player_last_name(candidate)
    if not last:
        return False
    collisions = [
        name
        for name in roster_names
        if player_last_name(name) == last
        and normalize_player_name(name) != normalize_player_name(candidate)
    ]
    if not collisions:
        return False
    # If full normalized name of the candidate is present, not a collision hit.
    if contains_phrase(article_text_blob.lower(), normalize_player_name(candidate)):
        return False
    return True


def valuation_safe_fields() -> frozenset[str]:
    """Fields news enrichment is allowed to write on article dicts."""

    return frozenset(
        {
            "title",
            "summary",
            "content",
            "description",
            "body",
            "link",
            "published",
            "published_parsed",
            "published_ts",
            "source",
            "matched_player",
            "relevance_reason",
            "relevance_score",
            "priority_score",
            "is_sleeper_update",
            "signal_events",
            "signal_primary_event",
            "signal_confidence",
            "signal_source_quality",
            "signal_speculative",
            "signal_notes",
            "signal_priority_adjustment",
            "event_identity",
        }
    )


def article_must_not_mutate_player_value() -> bool:
    """Contract marker used by tests — news never owns valuation math."""

    return True
