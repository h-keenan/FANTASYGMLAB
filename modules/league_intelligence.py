"""Pure presentation models for league-specific news intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from types import MappingProxyType
from typing import Callable, Mapping, MutableMapping, Sequence
from urllib.parse import urlparse

import pandas as pd


@dataclass(frozen=True)
class LeagueIntelligenceItem:
    item_id: str
    headline: str
    player_id: str
    player_name: str
    timestamp: float
    timestamp_label: str
    timeline_group: str
    source: str
    summary: str
    explanation: str
    relevance_reason: str
    league_relevance: str
    recommendation_label: str
    external_url: str


@dataclass(frozen=True)
class LeagueIntelligenceFeed:
    items: tuple[LeagueIntelligenceItem, ...]
    player_rows_by_id: Mapping[str, Mapping[str, object]]
    player_lookup_count: int


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


def _safe_external_url(value: object) -> str:
    url = _text(value)
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else ""


def _timeline_group(timestamp: float, now_timestamp: float) -> str:
    if timestamp <= 0:
        return "Recent updates"
    current = datetime.fromtimestamp(now_timestamp).date()
    published = datetime.fromtimestamp(timestamp).date()
    day_delta = (current - published).days
    if day_delta == 0:
        return "Today"
    if day_delta == 1:
        return "Yesterday"
    return published.strftime("%b %d, %Y")


def _recommendation_label(reason: str, league_relevance: str) -> str:
    normalized = reason.casefold()
    if "injury" in normalized:
        return "Injury Monitor"
    if league_relevance == "Available on waivers":
        return "Waiver Watch"
    return "Monitor"


def _owner_indexes(
    roster_player_map: Mapping[str, Sequence[str]],
) -> dict[str, str]:
    return {
        str(player_id): str(roster_id)
        for roster_id, player_ids in (roster_player_map or {}).items()
        for player_id in (player_ids or ())
    }


def roster_name_index(league_context: Mapping[str, object]) -> dict[str, str]:
    """Resolve existing display names without performing league calculations."""

    names: dict[str, str] = {}
    profiles = league_context.get("roster_profiles") or {}
    if isinstance(profiles, Mapping):
        for roster_id, profile in profiles.items():
            if isinstance(profile, Mapping):
                name = _text(
                    profile.get("team_name"),
                    _text(profile.get("display_name"), _text(profile.get("owner_name"))),
                )
                if name:
                    names[str(roster_id)] = name
    frame = league_context.get("league_intelligence_frame")
    if isinstance(frame, pd.DataFrame) and not frame.empty:
        for _, row in frame.iterrows():
            roster_id = _text(row.get("roster_id"))
            team_name = _text(row.get("team_name"), _text(row.get("owner_name")))
            if roster_id and team_name:
                names[roster_id] = team_name
    return names


def build_league_intelligence_feed(
    news_items: Sequence[Mapping[str, object]],
    players: pd.DataFrame,
    *,
    roster_player_map: Mapping[str, Sequence[str]],
    roster_names: Mapping[str, str],
    current_roster_id: str,
    summary_builder: Callable[[Mapping[str, object], int], str],
    relative_time_builder: Callable[[Mapping[str, object]], str],
    now_timestamp: float,
) -> LeagueIntelligenceFeed:
    """Join curated news to league ownership with one player-index construction."""

    name_to_ids: dict[str, list[str]] = {}
    rows_by_id: dict[str, Mapping[str, object]] = {}
    lookup_count = 0
    if players is not None and not players.empty:
        matched_names = {
            _text(item.get("matched_player")).casefold()
            for item in (news_items or ())
            if _text(item.get("matched_player"))
        }
        names = players.get(
            "name",
            pd.Series("", index=players.index),
        ).fillna("").astype(str).str.strip().str.casefold()
        matched_players = players[names.isin(matched_names)]
        for _, row in matched_players.iterrows():
            lookup_count += 1
            player_id = _text(row.get("player_id"))
            name = _text(row.get("name"))
            if not player_id or not name:
                continue
            frozen_row = MappingProxyType(row.to_dict())
            rows_by_id[player_id] = frozen_row
            name_to_ids.setdefault(name.casefold(), []).append(player_id)

    owner_by_player = _owner_indexes(roster_player_map)
    built: list[LeagueIntelligenceItem] = []
    seen_item_ids: set[str] = set()
    for raw_item in news_items or ():
        player_name = _text(raw_item.get("matched_player"))
        matched_ids = name_to_ids.get(player_name.casefold(), []) if player_name else []
        player_id = matched_ids[0] if len(matched_ids) == 1 else ""
        owner_id = owner_by_player.get(player_id, "") if player_id else ""
        if player_id and owner_id == str(current_roster_id):
            league_relevance = "Owned by you"
        elif player_id and owner_id:
            owner_name = _text(roster_names.get(owner_id))
            league_relevance = (
                f"Owned by {owner_name}" if owner_name else "Owned by another manager"
            )
        elif player_id:
            league_relevance = "Available on waivers"
        else:
            league_relevance = ""

        try:
            timestamp = float(raw_item.get("published_ts") or 0)
        except (TypeError, ValueError):
            timestamp = 0.0
        headline = _text(raw_item.get("title"), "Player update")
        reason = _text(raw_item.get("relevance_reason"), "player mention")
        summary = _text(summary_builder(raw_item, 220))
        expanded_summary = _text(summary_builder(raw_item, 900), summary)
        explanation_parts = [
            expanded_summary,
            f"League context: {league_relevance}." if league_relevance else "",
            f"Matched signal: {reason.replace('/', ' or ')}." if reason else "",
        ]
        explanation = " ".join(part for part in explanation_parts if part)
        identity = "\x1f".join(
            (
                _text(raw_item.get("link")),
                headline,
                str(timestamp),
                player_id or player_name,
            )
        )
        item_id = sha256(identity.encode("utf-8")).hexdigest()[:18]
        if item_id in seen_item_ids:
            continue
        seen_item_ids.add(item_id)
        built.append(
            LeagueIntelligenceItem(
                item_id=item_id,
                headline=headline,
                player_id=player_id,
                player_name=player_name,
                timestamp=timestamp,
                timestamp_label=_text(relative_time_builder(raw_item)),
                timeline_group=_timeline_group(timestamp, now_timestamp),
                source=_text(raw_item.get("source")),
                summary=summary,
                explanation=explanation,
                relevance_reason=reason,
                league_relevance=league_relevance,
                recommendation_label=_recommendation_label(reason, league_relevance),
                external_url=_safe_external_url(raw_item.get("link")),
            )
        )

    built.sort(
        key=lambda item: (item.timestamp, item.item_id),
        reverse=True,
    )
    return LeagueIntelligenceFeed(
        items=tuple(built),
        player_rows_by_id=MappingProxyType(rows_by_id),
        player_lookup_count=lookup_count,
    )


def disclosure_state_key(item_id: str) -> str:
    return f"league_intelligence_{item_id}_explanation_open"


def toggle_disclosure(
    item_id: str,
    *,
    state: MutableMapping[str, object],
) -> None:
    key = disclosure_state_key(item_id)
    state[key] = not bool(state.get(key, False))
