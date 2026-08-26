"""Canonical mutually exclusive My Team primary actions.

Shop / Hold / Drop / Untouchable are one-to-one for a player. Context
(upside, injury, depth, trade path) can remain on the winning row.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

ACTION_PROTECT = "protect"
ACTION_SHOP = "shop"
ACTION_DROP = "drop"
ACTION_HOLD = "hold"

# Manual protect wins.
# Headline / sell SHOP beats drop and hold (real trade path).
# Replacement-level DROP beats generic surplus SHOP and HOLD.
# Remaining SHOP beats HOLD. HOLD is the retain fallback.
PRECEDENCE = (ACTION_PROTECT, ACTION_SHOP, ACTION_DROP, ACTION_HOLD)


def _text(value: object, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def candidate_player_id(item: Mapping[str, Any] | None) -> str:
    if not isinstance(item, Mapping):
        return ""
    return _text(item.get("player_id"))


def candidate_player_name(item: Mapping[str, Any] | None) -> str:
    if not isinstance(item, Mapping):
        return ""
    return _text(item.get("player_name") or item.get("name"))


def _copy_items(items: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items or ():
        if not isinstance(item, Mapping):
            continue
        payload = dict(item)
        pid = candidate_player_id(payload)
        if pid and pid in seen:
            continue
        if pid:
            seen.add(pid)
        copied.append(payload)
    return copied


def _ids(items: Sequence[Mapping[str, Any]]) -> set[str]:
    return {candidate_player_id(item) for item in items if candidate_player_id(item)}


def _names(items: Sequence[Mapping[str, Any]]) -> set[str]:
    return {candidate_player_name(item) for item in items if candidate_player_name(item)}


def _exclude(
    items: Sequence[Mapping[str, Any]],
    *,
    banned_ids: Iterable[str] | None = None,
    banned_names: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    blocked_ids = {str(pid).strip() for pid in (banned_ids or ()) if str(pid).strip()}
    blocked_names = {str(name).strip() for name in (banned_names or ()) if str(name).strip()}
    kept: list[dict[str, Any]] = []
    for item in items:
        pid = candidate_player_id(item)
        name = candidate_player_name(item)
        if pid and pid in blocked_ids:
            continue
        if name and name in blocked_names:
            continue
        kept.append(dict(item))
    return kept


def _reprioritize(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        payload = dict(item)
        payload["priority"] = index
        ranked.append(payload)
    return ranked


def conflicting_primary_player_ids(
    *,
    trade_candidates: Sequence[Mapping[str, Any]] | None = None,
    keep_candidates: Sequence[Mapping[str, Any]] | None = None,
    drop_candidates: Sequence[Mapping[str, Any]] | None = None,
) -> set[str]:
    """Players present in more than one exclusive primary-action list."""

    shop = _ids(_copy_items(trade_candidates))
    hold = _ids(_copy_items(keep_candidates))
    drop = _ids(_copy_items(drop_candidates))
    conflicts: set[str] = set()
    conflicts.update(shop & hold)
    conflicts.update(shop & drop)
    conflicts.update(hold & drop)
    return conflicts


def reconcile_primary_action_lists(
    *,
    trade_candidates: Sequence[Mapping[str, Any]] | None = None,
    keep_candidates: Sequence[Mapping[str, Any]] | None = None,
    drop_candidates: Sequence[Mapping[str, Any]] | None = None,
    untouchable_player_ids: Iterable[str] | None = None,
    untouchable_names: Iterable[str] | None = None,
    max_items: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    """Return exclusive shop / hold / drop lists. Does not invent new candidates."""

    shop = _copy_items(trade_candidates)
    hold = _copy_items(keep_candidates)
    drop = _copy_items(drop_candidates)
    protect_ids = {str(pid).strip() for pid in (untouchable_player_ids or ()) if str(pid).strip()}
    protect_names = {str(name).strip() for name in (untouchable_names or ()) if str(name).strip()}

    shop = _exclude(shop, banned_ids=protect_ids, banned_names=protect_names)
    hold = _exclude(hold, banned_ids=protect_ids, banned_names=protect_names)
    drop = _exclude(drop, banned_ids=protect_ids, banned_names=protect_names)

    headline_shop = [
        item
        for item in shop
        if _text(item.get("source")) in {"headline_trade", "sell_candidate"}
    ]
    roster_shop = [
        item
        for item in shop
        if _text(item.get("source")) not in {"headline_trade", "sell_candidate"}
    ]
    headline_ids = _ids(headline_shop)
    headline_names = _names(headline_shop)
    drop = _exclude(drop, banned_ids=headline_ids, banned_names=headline_names)
    hold = _exclude(hold, banned_ids=headline_ids, banned_names=headline_names)

    drop_ids = _ids(drop)
    drop_names = _names(drop)
    roster_shop = _exclude(roster_shop, banned_ids=drop_ids, banned_names=drop_names)
    hold = _exclude(hold, banned_ids=drop_ids, banned_names=drop_names)

    shop = headline_shop + roster_shop
    shop_ids = _ids(shop)
    shop_names = _names(shop)
    hold = _exclude(hold, banned_ids=shop_ids, banned_names=shop_names)

    cap = max(1, int(max_items or 3))
    return {
        ACTION_SHOP: _reprioritize(shop[:cap]),
        ACTION_HOLD: _reprioritize(hold[:cap]),
        ACTION_DROP: _reprioritize(drop[:cap]),
        ACTION_PROTECT: [],
    }


def primary_action_for_player(
    player_id: str,
    *,
    trade_candidates: Sequence[Mapping[str, Any]] | None = None,
    keep_candidates: Sequence[Mapping[str, Any]] | None = None,
    drop_candidates: Sequence[Mapping[str, Any]] | None = None,
    untouchable_player_ids: Iterable[str] | None = None,
    untouchable_names: Iterable[str] | None = None,
    player_name: str = "",
) -> str:
    pid = str(player_id or "").strip()
    name = str(player_name or "").strip()
    protect_ids = {str(item).strip() for item in (untouchable_player_ids or ()) if str(item).strip()}
    protect_names = {str(item).strip() for item in (untouchable_names or ()) if str(item).strip()}
    if (pid and pid in protect_ids) or (name and name in protect_names):
        return ACTION_PROTECT
    lists = reconcile_primary_action_lists(
        trade_candidates=trade_candidates,
        keep_candidates=keep_candidates,
        drop_candidates=drop_candidates,
        untouchable_player_ids=protect_ids,
        untouchable_names=protect_names,
    )
    if pid and pid in _ids(lists[ACTION_SHOP]):
        return ACTION_SHOP
    if pid and pid in _ids(lists[ACTION_DROP]):
        return ACTION_DROP
    if pid and pid in _ids(lists[ACTION_HOLD]):
        return ACTION_HOLD
    return ""
