"""Deterministic league storylines from normalized History transactions.

Presentation-free. No valuation, no winner/loser labels, no provider calls.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from modules import league_history as history


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


def _roster_id(value: object) -> int:
    parsed = _int(value, 0)
    return parsed if parsed > 0 else 0


def _tx_id(transaction: Mapping[str, Any]) -> str:
    return _text(transaction.get("transaction_id"))


def _identity_from_side(side: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(side, Mapping):
        return {
            "roster_id": "",
            "team_name": "Unknown team",
            "owner_handle": "",
            "avatar_url": "",
        }
    roster_id = _text(side.get("roster_id"))
    name = _text(side.get("team_name"), "Unknown team")
    if name.casefold().startswith("team ") and name[5:].isdigit():
        name = "Unknown team"
    handle = _text(side.get("owner_handle"))
    return {
        "roster_id": roster_id,
        "team_name": name or "Unknown team",
        "owner_handle": handle,
        "avatar_url": _text(side.get("avatar_url")),
    }


def _identities(transactions: Sequence[Mapping[str, Any]], profiles: Mapping[str, Any] | None) -> dict[int, dict[str, str]]:
    found: dict[int, dict[str, str]] = {}
    if isinstance(profiles, Mapping):
        for key, row in profiles.items():
            roster_id = _roster_id(key if not isinstance(row, Mapping) else row.get("roster_id") or key)
            if not roster_id:
                continue
            payload = row if isinstance(row, Mapping) else {}
            handle = _text(payload.get("username"))
            if handle and not handle.startswith("@"):
                handle = f"@{handle}"
            elif not handle:
                handle = _text(payload.get("owner_name"))
            name = _text(payload.get("team_name"), "Unknown team")
            found[roster_id] = {
                "roster_id": str(roster_id),
                "team_name": name or "Unknown team",
                "owner_handle": handle,
                "avatar_url": _text(payload.get("avatar_url")),
            }
    for transaction in transactions:
        for side in transaction.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            roster_id = _roster_id(side.get("roster_id"))
            if not roster_id:
                continue
            identity = _identity_from_side(side)
            current = found.get(roster_id)
            if current is None or current.get("team_name") == "Unknown team":
                found[roster_id] = identity
    return found


def _tie_key(identity: Mapping[str, Any], roster_id: int) -> tuple:
    return (_text(identity.get("team_name")).casefold(), roster_id)


def _pick_leader(scored: Sequence[tuple[int, int, Mapping[str, Any]]]) -> dict[str, Any] | None:
    """scored items are (metric, roster_id, identity). Highest metric wins."""

    eligible = [item for item in scored if item[0] > 0 and item[1] > 0]
    if not eligible:
        return None
    eligible.sort(key=lambda item: (-item[0], *_tie_key(item[2], item[1])))
    metric, roster_id, identity = eligible[0]
    tied = sum(1 for item in eligible if item[0] == metric)
    return {
        "roster_id": str(roster_id),
        "metric": metric,
        "tied": tied > 1,
        **identity,
    }


def transaction_activity_by_roster(
    transactions: Sequence[Mapping[str, Any]],
) -> dict[int, dict[str, int]]:
    """Unique completed transactions per roster, with type breakdown.

    A roster is counted once per transaction_id even if it appears in both
    adds and drops.
    """

    buckets: dict[int, dict[str, int]] = {}
    seen: dict[int, set[str]] = defaultdict(set)
    for transaction in transactions:
        tx_id = _tx_id(transaction)
        if not tx_id:
            continue
        tx_type = _text(transaction.get("type")).casefold()
        roster_ids = {_roster_id(value) for value in (transaction.get("roster_ids") or [])}
        for side in transaction.get("sides") or []:
            if isinstance(side, Mapping):
                roster_ids.add(_roster_id(side.get("roster_id")))
        for roster_id in roster_ids:
            if roster_id <= 0 or tx_id in seen[roster_id]:
                continue
            seen[roster_id].add(tx_id)
            bucket = buckets.setdefault(
                roster_id,
                {"total": 0, "trade": 0, "waiver": 0, "free_agent": 0},
            )
            bucket["total"] += 1
            if tx_type in bucket:
                bucket[tx_type] += 1
    return buckets


def completed_trade_count_by_roster(
    transactions: Sequence[Mapping[str, Any]],
) -> dict[int, int]:
    counts: dict[int, int] = {}
    seen: dict[int, set[str]] = defaultdict(set)
    for transaction in transactions:
        if _text(transaction.get("type")).casefold() != "trade":
            continue
        tx_id = _tx_id(transaction)
        if not tx_id:
            continue
        roster_ids = {_roster_id(value) for value in (transaction.get("roster_ids") or [])}
        for side in transaction.get("sides") or []:
            if isinstance(side, Mapping):
                roster_ids.add(_roster_id(side.get("roster_id")))
        for roster_id in roster_ids:
            if roster_id <= 0 or tx_id in seen[roster_id]:
                continue
            seen[roster_id].add(tx_id)
            counts[roster_id] = counts.get(roster_id, 0) + 1
    return counts


def incoming_pick_count_by_roster(
    transactions: Sequence[Mapping[str, Any]],
) -> dict[int, int]:
    """Picks received in completed trades, not current ownership."""

    counts: dict[int, int] = {}
    for transaction in transactions:
        if _text(transaction.get("type")).casefold() != "trade":
            continue
        for pick in transaction.get("draft_picks") or []:
            if not isinstance(pick, Mapping):
                continue
            roster_id = _roster_id(pick.get("to_roster_id") or pick.get("roster_id"))
            if roster_id <= 0:
                continue
            counts[roster_id] = counts.get(roster_id, 0) + 1
    return counts


def faab_spend_by_roster(transactions: Sequence[Mapping[str, Any]]) -> dict[int, int]:
    totals: dict[int, int] = {}
    seen: set[str] = set()
    for transaction in transactions:
        tx_id = _tx_id(transaction)
        if tx_id in seen:
            continue
        if tx_id:
            seen.add(tx_id)
        if _text(transaction.get("type")).casefold() != "waiver":
            continue
        bid = transaction.get("waiver_bid")
        amount = _int(bid, 0) if bid not in (None, "") else 0
        if amount <= 0:
            continue
        spenders = []
        for side in transaction.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            if _int(side.get("faab_spent"), 0) > 0 or side.get("receives"):
                spenders.append(_roster_id(side.get("roster_id")))
        if not spenders:
            for roster_id in transaction.get("roster_ids") or []:
                spenders.append(_roster_id(roster_id))
        roster_id = next((item for item in spenders if item > 0), 0)
        if roster_id:
            totals[roster_id] = totals.get(roster_id, 0) + amount
    return totals


def roster_turnover(transactions: Sequence[Mapping[str, Any]]) -> dict[int, int]:
    """Player-asset changes per roster.

    For each completed transaction, count unique player IDs on that roster's
    adds ∪ drops. The same player listed as both add and drop in one
    transaction counts once. Picks are excluded.
    """

    totals: dict[int, int] = {}
    seen_tx: dict[int, set[str]] = defaultdict(set)
    for transaction in transactions:
        tx_id = _tx_id(transaction) or f"anon:{id(transaction)}"
        by_roster: dict[int, set[str]] = defaultdict(set)
        for asset in list(transaction.get("adds") or []) + list(transaction.get("drops") or []):
            if not isinstance(asset, Mapping) or _text(asset.get("kind"), "player") == "pick":
                continue
            player_id = _text(asset.get("player_id") or asset.get("name"))
            roster_id = _roster_id(asset.get("roster_id"))
            if roster_id <= 0 or not player_id:
                continue
            by_roster[roster_id].add(player_id)
        for roster_id, players in by_roster.items():
            if tx_id in seen_tx[roster_id]:
                continue
            seen_tx[roster_id].add(tx_id)
            totals[roster_id] = totals.get(roster_id, 0) + len(players)
    return totals


def trade_package_size(transaction: Mapping[str, Any]) -> dict[str, int]:
    players = [
        asset
        for asset in (transaction.get("adds") or [])
        if isinstance(asset, Mapping) and _text(asset.get("kind"), "player") != "pick"
    ]
    picks = [
        asset
        for asset in (transaction.get("draft_picks") or [])
        if isinstance(asset, Mapping)
    ]
    return {
        "players": len(players),
        "picks": len(picks),
        "assets": len(players) + len(picks),
    }


def largest_trade(transactions: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    ranked: list[tuple] = []
    seen: set[str] = set()
    for transaction in transactions:
        if _text(transaction.get("type")).casefold() != "trade":
            continue
        tx_id = _tx_id(transaction)
        if tx_id and tx_id in seen:
            continue
        if tx_id:
            seen.add(tx_id)
        size = trade_package_size(transaction)
        if size["assets"] <= 0:
            continue
        ranked.append(
            (
                -size["assets"],
                -size["picks"],
                -size["players"],
                -_int(transaction.get("timestamp"), 0),
                tx_id,
                transaction,
                size,
            )
        )
    if not ranked:
        return None
    ranked.sort()
    _neg_assets, _neg_picks, _neg_players, _neg_ts, tx_id, transaction, size = ranked[0]
    teams = []
    seen_teams: set[str] = set()
    for side in transaction.get("sides") or []:
        if not isinstance(side, Mapping):
            continue
        identity = _identity_from_side(side)
        key = identity["roster_id"] or identity["team_name"]
        if key in seen_teams:
            continue
        seen_teams.add(key)
        teams.append(identity)
    return {
        "transaction_id": tx_id,
        "week": _int(transaction.get("week"), 0),
        "timestamp": _int(transaction.get("timestamp"), 0),
        "when": history.format_history_when(
            week=_int(transaction.get("week"), 0),
            timestamp_ms=_int(transaction.get("timestamp"), 0),
        ),
        "teams": teams,
        **size,
    }


def biggest_faab_spend(transactions: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    ranked: list[tuple] = []
    seen: set[str] = set()
    for transaction in transactions:
        if _text(transaction.get("type")).casefold() != "waiver":
            continue
        tx_id = _tx_id(transaction)
        if tx_id and tx_id in seen:
            continue
        if tx_id:
            seen.add(tx_id)
        amount = _int(transaction.get("waiver_bid"), 0)
        if amount <= 0:
            continue
        spender = None
        player = None
        for side in transaction.get("sides") or []:
            if not isinstance(side, Mapping):
                continue
            receives = [asset for asset in (side.get("receives") or []) if isinstance(asset, Mapping)]
            if receives or _int(side.get("faab_spent"), 0) > 0:
                spender = _identity_from_side(side)
                player = receives[0] if receives else None
                break
        if spender is None:
            continue
        ranked.append(
            (
                -amount,
                -_int(transaction.get("timestamp"), 0),
                tx_id,
                spender,
                player,
                transaction,
            )
        )
    if not ranked:
        return None
    ranked.sort()
    amount, _ts, tx_id, spender, player, transaction = ranked[0]
    return {
        "amount": -amount,
        "transaction_id": tx_id,
        "week": _int(transaction.get("week"), 0),
        "timestamp": _int(transaction.get("timestamp"), 0),
        "when": history.format_history_when(
            week=_int(transaction.get("week"), 0),
            timestamp_ms=_int(transaction.get("timestamp"), 0),
        ),
        "player": player or {},
        **spender,
    }


def busiest_week(transactions: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    counts: Counter[int] = Counter()
    seen: set[str] = set()
    for transaction in transactions:
        tx_id = _tx_id(transaction)
        if tx_id and tx_id in seen:
            continue
        if tx_id:
            seen.add(tx_id)
        week = _int(transaction.get("week"), 0)
        if week > 0:
            counts[week] += 1
    if not counts:
        return None
    week, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    if count < 3:
        return None
    return {"week": week, "count": count}


def most_traded_player(transactions: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    counts: Counter[str] = Counter()
    samples: dict[str, Mapping[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    for transaction in transactions:
        if _text(transaction.get("type")).casefold() != "trade":
            continue
        tx_id = _tx_id(transaction)
        for asset in list(transaction.get("adds") or []) + list(transaction.get("drops") or []):
            if not isinstance(asset, Mapping) or _text(asset.get("kind"), "player") == "pick":
                continue
            player_id = _text(asset.get("player_id") or asset.get("name"))
            if not player_id:
                continue
            key = (tx_id, player_id)
            if key in seen:
                continue
            seen.add(key)
            counts[player_id] += 1
            samples[player_id] = asset
    if not counts:
        return None
    player_id, count = sorted(
        counts.items(),
        key=lambda item: (-item[1], _text(samples.get(item[0], {}).get("name")).casefold(), item[0]),
    )[0]
    if count < 2:
        return None
    asset = dict(samples.get(player_id) or {})
    return {"count": count, "player": asset}


def build_league_storylines(
    transactions: Sequence[Mapping[str, Any]],
    *,
    profiles: Mapping[str, Any] | None = None,
    season: str = "",
) -> dict[str, Any]:
    """Assemble the v1 storyline set for one season's normalized history."""

    identities = _identities(transactions, profiles)
    activity = transaction_activity_by_roster(transactions)
    trades = completed_trade_count_by_roster(transactions)
    picks = incoming_pick_count_by_roster(transactions)
    turnover = roster_turnover(transactions)
    faab_totals = faab_spend_by_roster(transactions)

    def _scored(mapping: Mapping[int, Any], field: str | None = None) -> list[tuple[int, int, Mapping[str, Any]]]:
        rows = []
        for roster_id, value in mapping.items():
            metric = _int(value.get(field) if field and isinstance(value, Mapping) else value, 0)
            rows.append((metric, roster_id, identities.get(roster_id, {
                "roster_id": str(roster_id),
                "team_name": "Unknown team",
                "owner_handle": "",
                "avatar_url": "",
            })))
        return rows

    most_active = _pick_leader(_scored(activity, "total"))
    if most_active:
        bucket = activity.get(_roster_id(most_active["roster_id"]), {})
        most_active["breakdown"] = {
            "trade": _int(bucket.get("trade"), 0),
            "waiver": _int(bucket.get("waiver"), 0),
            "free_agent": _int(bucket.get("free_agent"), 0),
        }

    quietest = None
    if len(identities) >= 3 and any(_int(row.get("total"), 0) > 0 for row in activity.values()):
        quiet_rows = []
        for roster_id, identity in identities.items():
            total = _int(activity.get(roster_id, {}).get("total"), 0)
            quiet_rows.append((total, roster_id, identity))
        quiet_rows.sort(key=lambda item: (item[0], *_tie_key(item[2], item[1])))
        low, roster_id, identity = quiet_rows[0]
        leader_total = _int((most_active or {}).get("metric"), 0)
        if leader_total > low:
            quietest = {**identity, "roster_id": str(roster_id), "metric": low, "tied": False}

    peak_activity = max((_int(row.get("total"), 0) for row in activity.values()), default=0)
    peak_trades = max(trades.values(), default=0)
    peak_picks = max(picks.values(), default=0)
    peak_turnover = max(turnover.values(), default=0)

    return {
        "season": _text(season),
        "transaction_count": len({_tx_id(item) or id(item) for item in transactions}),
        "most_active": most_active,
        "trade_market_leader": _pick_leader(_scored(trades)),
        "most_picks_acquired": _pick_leader(_scored(picks)),
        "roster_turnover": _pick_leader(_scored(turnover)),
        "largest_trade": largest_trade(transactions),
        "biggest_faab": biggest_faab_spend(transactions),
        "faab_leader": _pick_leader(_scored(faab_totals)),
        "quietest": quietest,
        "busiest_week": busiest_week(transactions),
        "most_traded_player": most_traded_player(transactions),
        "peaks": {
            "activity": peak_activity,
            "trades": peak_trades,
            "picks": peak_picks,
            "turnover": peak_turnover,
        },
    }
