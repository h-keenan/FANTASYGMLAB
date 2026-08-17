"""Canonical league transaction history — normalize Sleeper payloads only.

No valuation, no winner/loser labels, no invented events.
Provider calls belong to the History route via injected fetchers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence


HISTORY_TYPES = frozenset({"trade", "waiver", "free_agent"})
COMPLETE_STATUSES = frozenset({"complete", "accepted", "processed"})
FILTER_ALL = "All"
FILTER_TRADES = "Trades"
FILTER_WAIVERS = "Waivers"
FILTER_FREE_AGENTS = "Free Agents"
FILTER_PICKS = "Picks"
HISTORY_FILTERS = (
    FILTER_ALL,
    FILTER_TRADES,
    FILTER_WAIVERS,
    FILTER_FREE_AGENTS,
    FILTER_PICKS,
)
MAX_SEASON_CHAIN = 10
MAX_TRANSACTION_WEEK = 18

FetchLeague = Callable[[str], Mapping[str, Any] | None]
FetchTransactions = Callable[[str, int], Sequence[Mapping[str, Any]] | None]
FetchProfiles = Callable[[str], Mapping[str, Any] | None]


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _positive_int(value: object, default: int = 0) -> int:
    parsed = _int(value, default)
    return parsed if parsed > 0 else default


def round_label(round_num: object) -> str:
    number = _positive_int(round_num, 0)
    if number <= 0:
        return ""
    suffix = "th"
    if number % 100 not in {11, 12, 13}:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def pick_label(pick: Mapping[str, Any] | None) -> str:
    if not isinstance(pick, Mapping):
        return "Draft pick"
    season = _text(pick.get("season"))
    labeled_round = round_label(pick.get("round"))
    if season and labeled_round:
        return f"{season} {labeled_round}"
    if season:
        return f"{season} pick"
    if labeled_round:
        return f"{labeled_round} round pick"
    return "Draft pick"


def format_history_when(*, week: int, timestamp_ms: int) -> str:
    parts: list[str] = []
    if week > 0:
        parts.append(f"Week {week}")
    if timestamp_ms > 0:
        try:
            instant = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            parts.append(f"{instant.strftime('%b')} {instant.day}, {instant.year}")
        except (OSError, OverflowError, ValueError):
            pass
    return " · ".join(parts) if parts else "Date unavailable"


def transaction_week_span(league: Mapping[str, Any] | None) -> int:
    """How many Sleeper transaction weeks to request for one league season."""

    if not isinstance(league, Mapping) or not league:
        return 1
    settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    status = _text(league.get("status")).casefold()

    def _setting(key: str, default: int = 0) -> int:
        return max(0, _int(settings.get(key), default))

    last_scored = _setting("last_scored_leg")
    leg = _setting("leg")
    playoff_start = _setting("playoff_week_start", 15)
    if status in {"complete", "completed"}:
        return min(
            MAX_TRANSACTION_WEEK,
            max(last_scored, playoff_start + 3, 17, 1),
        )
    if last_scored > 0:
        return min(MAX_TRANSACTION_WEEK, max(last_scored, leg, 1))
    if leg > 0:
        return min(MAX_TRANSACTION_WEEK, leg)
    return 1


def walk_season_chain(
    start_league_id: str,
    fetch_league: FetchLeague,
    *,
    max_seasons: int = MAX_SEASON_CHAIN,
) -> list[dict[str, Any]]:
    """Follow previous_league_id. Does not invent missing seasons."""

    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    current = _text(start_league_id)
    while current and current not in seen and len(chain) < max(1, max_seasons):
        seen.add(current)
        league = fetch_league(current) or {}
        if not isinstance(league, Mapping) or not league:
            break
        season = _text(league.get("season"))
        chain.append(
            {
                "league_id": current,
                "season": season,
                "name": _text(league.get("name"), "League"),
                "status": _text(league.get("status")),
                "previous_league_id": _text(league.get("previous_league_id")),
                "week_span": transaction_week_span(league),
            }
        )
        current = _text(league.get("previous_league_id"))
    return chain


def _profile_row(profiles: Mapping[str, Any], roster_id: int) -> dict[str, str]:
    raw = profiles.get(str(roster_id)) or profiles.get(roster_id) or {}
    if not isinstance(raw, Mapping):
        raw = {}
    team_name = _text(raw.get("team_name"), "Unknown team")
    handle = _text(raw.get("username"))
    owner_name = _text(raw.get("owner_name"))
    if handle and not handle.startswith("@"):
        handle = f"@{handle}"
    elif not handle:
        handle = owner_name
    return {
        "roster_id": str(roster_id),
        "team_name": team_name or "Unknown team",
        "owner_handle": handle,
        "avatar_url": _text(raw.get("avatar_url")),
    }


def _player_asset(
    player_id: object,
    roster_id: int,
    player_lookup: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    key = _text(player_id)
    row = player_lookup.get(key) if key else None
    if not isinstance(row, Mapping):
        row = {}
    name = _text(row.get("name") or row.get("full_name"))
    known = bool(name)
    if not name:
        name = "Unavailable player"
    return {
        "kind": "player",
        "player_id": key if known else "",
        "name": name,
        "position": _text(row.get("position")).upper(),
        "team": _text(row.get("team") or row.get("nfl_team")).upper(),
        "label": name,
        "roster_id": roster_id,
        "known": known,
    }


def _pick_asset(pick: Mapping[str, Any], *, to_roster_id: int, from_roster_id: int) -> dict[str, Any]:
    label = pick_label(pick)
    return {
        "kind": "pick",
        "player_id": "",
        "name": label,
        "position": "",
        "team": "",
        "season": _text(pick.get("season")),
        "round": _positive_int(pick.get("round"), 0) or None,
        "label": label,
        "roster_id": to_roster_id,
        "from_roster_id": from_roster_id,
        "to_roster_id": to_roster_id,
    }


def _roster_set(*groups: Iterable[object]) -> list[int]:
    ordered: list[int] = []
    seen: set[int] = set()
    for group in groups:
        for value in group:
            roster_id = _positive_int(value, 0)
            if roster_id and roster_id not in seen:
                seen.add(roster_id)
                ordered.append(roster_id)
    return ordered


def _map_ids(payload: object) -> dict[str, int]:
    if not isinstance(payload, Mapping):
        return {}
    mapped: dict[str, int] = {}
    for key, value in payload.items():
        roster_id = _positive_int(value, 0)
        player_id = _text(key)
        if player_id and roster_id:
            mapped[player_id] = roster_id
    return mapped


def _waiver_bid(transaction: Mapping[str, Any]) -> int | None:
    settings = transaction.get("settings") if isinstance(transaction.get("settings"), dict) else {}
    metadata = transaction.get("metadata") if isinstance(transaction.get("metadata"), dict) else {}
    for source in (settings, metadata, transaction):
        if not isinstance(source, Mapping):
            continue
        if "waiver_bid" not in source:
            continue
        amount = _int(source.get("waiver_bid"), 0)
        if amount > 0:
            return amount
        return 0
    return None


def _waiver_budget_rows(transaction: Mapping[str, Any]) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    raw = transaction.get("waiver_budget")
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        amount = _int(item.get("amount"), 0)
        sender = _positive_int(item.get("sender") or item.get("sender_id"), 0)
        receiver = _positive_int(item.get("receiver") or item.get("receiver_id"), 0)
        if amount == 0 and not sender and not receiver:
            continue
        rows.append(
            {
                "from_roster_id": sender,
                "to_roster_id": receiver,
                "amount": amount,
            }
        )
    return rows


def normalize_transaction(
    transaction: Mapping[str, Any] | None,
    *,
    league_id: str,
    season: str,
    week: int,
    profiles: Mapping[str, Any],
    player_lookup: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(transaction, Mapping):
        return None
    tx_type = _text(transaction.get("type")).casefold()
    status = _text(transaction.get("status")).casefold()
    if tx_type not in HISTORY_TYPES or status not in COMPLETE_STATUSES:
        return None

    adds = _map_ids(transaction.get("adds"))
    drops = _map_ids(transaction.get("drops"))
    raw_picks = transaction.get("draft_picks") if isinstance(transaction.get("draft_picks"), list) else []
    pick_assets: list[dict[str, Any]] = []
    pick_to: list[int] = []
    pick_from: list[int] = []
    for pick in raw_picks:
        if not isinstance(pick, Mapping):
            continue
        to_roster = _positive_int(pick.get("owner_id"), 0)
        from_roster = _positive_int(pick.get("previous_owner_id"), 0)
        if not to_roster:
            continue
        pick_assets.append(
            _pick_asset(pick, to_roster_id=to_roster, from_roster_id=from_roster)
        )
        pick_to.append(to_roster)
        if from_roster:
            pick_from.append(from_roster)

    roster_ids = _roster_set(
        transaction.get("roster_ids") or [],
        adds.values(),
        drops.values(),
        pick_to,
        pick_from,
    )
    add_assets = [
        _player_asset(player_id, roster_id, player_lookup)
        for player_id, roster_id in adds.items()
    ]
    drop_assets = [
        _player_asset(player_id, roster_id, player_lookup)
        for player_id, roster_id in drops.items()
    ]
    if not add_assets and not drop_assets and not pick_assets:
        return None

    bid = _waiver_bid(transaction)
    budget = _waiver_budget_rows(transaction)
    timestamp = _int(transaction.get("status_updated") or transaction.get("created"), 0)
    tx_id = _text(transaction.get("transaction_id") or transaction.get("id"))
    if not tx_id:
        tx_id = f"{league_id}:{week}:{timestamp}:{tx_type}"

    sides: list[dict[str, Any]] = []
    for roster_id in roster_ids:
        receives = [asset for asset in add_assets if asset.get("roster_id") == roster_id]
        receives.extend(
            asset for asset in pick_assets if asset.get("to_roster_id") == roster_id
        )
        side_drops = [asset for asset in drop_assets if asset.get("roster_id") == roster_id]
        faab_spent = None
        faab_received = None
        if bid is not None and tx_type == "waiver" and receives:
            faab_spent = bid
        for row in budget:
            if row.get("from_roster_id") == roster_id and row.get("amount"):
                faab_spent = (faab_spent or 0) + int(row["amount"])
            if row.get("to_roster_id") == roster_id and row.get("amount"):
                faab_received = (faab_received or 0) + int(row["amount"])
        identity = _profile_row(profiles, roster_id)
        sides.append(
            {
                **identity,
                "receives": receives,
                "drops": side_drops,
                "faab_spent": faab_spent,
                "faab_received": faab_received,
            }
        )

    return {
        "transaction_id": tx_id,
        "season": season,
        "league_id": league_id,
        "week": week,
        "timestamp": timestamp,
        "type": tx_type,
        "status": status,
        "roster_ids": roster_ids,
        "adds": add_assets,
        "drops": drop_assets,
        "draft_picks": pick_assets,
        "waiver_budget": budget,
        "waiver_bid": bid,
        "sides": sides,
        "metadata": {
            "creator": _text(transaction.get("creator")),
            "consenter_ids": list(transaction.get("consenter_ids") or []),
        },
    }


def collect_season_transactions(
    league_id: str,
    *,
    fetch_league: FetchLeague,
    fetch_transactions: FetchTransactions,
    week_span: int | None = None,
) -> dict[str, Any]:
    league = fetch_league(league_id) or {}
    season = _text(league.get("season")) if isinstance(league, Mapping) else ""
    span = week_span if week_span is not None else transaction_week_span(league)
    span = max(1, min(MAX_TRANSACTION_WEEK, _int(span, 1)))
    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for week in range(1, span + 1):
        rows = fetch_transactions(league_id, week) or []
        for raw in rows:
            if not isinstance(raw, Mapping):
                continue
            item = dict(raw)
            item["_history_week"] = week
            tx_id = _text(item.get("transaction_id") or item.get("id"))
            dedupe = tx_id or f"{week}:{item.get('status_updated')}:{item.get('type')}"
            if dedupe in seen_ids:
                continue
            seen_ids.add(dedupe)
            collected.append(item)
    return {
        "league_id": _text(league_id),
        "season": season,
        "name": _text(league.get("name"), "League") if isinstance(league, Mapping) else "League",
        "weeks_fetched": span,
        "transactions": collected,
    }


def normalize_season_payload(
    payload: Mapping[str, Any],
    *,
    profiles: Mapping[str, Any],
    player_lookup: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    league_id = _text(payload.get("league_id"))
    season = _text(payload.get("season"))
    normalized: list[dict[str, Any]] = []
    for raw in payload.get("transactions") or []:
        week = _positive_int(
            raw.get("_history_week") or raw.get("leg") or raw.get("week"),
            0,
        )
        item = normalize_transaction(
            raw,
            league_id=league_id,
            season=season,
            week=week,
            profiles=profiles,
            player_lookup=player_lookup,
        )
        if item:
            normalized.append(item)
    normalized.sort(
        key=lambda row: (
            int(row.get("timestamp") or 0),
            int(row.get("week") or 0),
            str(row.get("transaction_id") or ""),
        ),
        reverse=True,
    )
    return normalized


def matches_history_filter(transaction: Mapping[str, Any], selected: str) -> bool:
    label = _text(selected, FILTER_ALL)
    tx_type = _text(transaction.get("type")).casefold()
    if label in {FILTER_ALL, ""}:
        return True
    if label == FILTER_TRADES:
        return tx_type == "trade"
    if label == FILTER_WAIVERS:
        return tx_type == "waiver"
    if label == FILTER_FREE_AGENTS:
        return tx_type == "free_agent"
    if label == FILTER_PICKS:
        return bool(transaction.get("draft_picks"))
    return True


def filter_history(
    transactions: Sequence[Mapping[str, Any]],
    selected: str,
) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in transactions
        if matches_history_filter(item, selected)
    ]


def player_lookup_from_rows(rows: Iterable[Mapping[str, Any]] | None) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        player_id = _text(row.get("player_id"))
        if not player_id:
            continue
        lookup[player_id] = {
            "name": _text(row.get("name") or row.get("full_name"), "Unavailable player"),
            "position": _text(row.get("position")),
            "team": _text(row.get("team")),
        }
    return lookup
