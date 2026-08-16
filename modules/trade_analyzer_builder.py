"""Incoming-offer Trade Analyzer package mutation.

Presentation/state only — no valuation, rankings, or provider calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence


SEND_KEY = "trade_send_assets"
RECEIVE_KEY = "trade_receive_assets"


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def asset_identity(asset: Mapping[str, Any] | None) -> str:
    if not isinstance(asset, Mapping):
        return ""
    if _text(asset.get("asset_type")) == "player":
        player_id = _text(asset.get("player_id"))
        return f"player:{player_id}" if player_id else ""
    return (
        "pick:"
        f"{_text(asset.get('season'))}:"
        f"{_text(asset.get('round'))}:"
        f"{_text(asset.get('owner_roster_id'))}:"
        f"{_text(asset.get('label') or asset.get('name'))}"
    )


def package_identities(assets: Sequence[Mapping[str, Any]] | None) -> set[str]:
    return {
        asset_identity(asset)
        for asset in (assets or [])
        if isinstance(asset, Mapping) and asset_identity(asset)
    }


def receive_owner_ids(assets: Sequence[Mapping[str, Any]] | None) -> list[str]:
    return sorted(
        {
            _text(asset.get("owner_roster_id"))
            for asset in (assets or [])
            if isinstance(asset, Mapping) and _text(asset.get("owner_roster_id"))
        }
    )


def widget_key_token(identity: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in identity)[:80] or "asset"


@dataclass(frozen=True)
class PackageMutation:
    ok: bool
    notice: str
    send_assets: list[dict[str, Any]]
    receive_assets: list[dict[str, Any]]
    added_label: str = ""
    invalidate_result: bool = False


def _copy_package(assets: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(asset) for asset in (assets or []) if isinstance(asset, Mapping)]


def try_add_asset(
    asset: Mapping[str, Any],
    *,
    package_key: str,
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
    partner_roster_id: str = "",
    my_roster_id: str = "",
) -> PackageMutation:
    """Add one asset with duplicate / cross-side / ownership guards."""

    send = _copy_package(send_assets)
    receive = _copy_package(receive_assets)
    payload = dict(asset)
    identity = asset_identity(payload)
    label = _text(payload.get("name") or payload.get("label"), "Asset")
    target = receive if package_key == RECEIVE_KEY else send
    other = send if package_key == RECEIVE_KEY else receive

    if identity and identity in package_identities(target):
        return PackageMutation(False, "That asset is already in this package.", send, receive)
    if identity and identity in package_identities(other):
        return PackageMutation(
            False,
            "That asset is already on the other side of the trade.",
            send,
            receive,
        )
    owner_id = _text(payload.get("owner_roster_id"))
    if package_key == RECEIVE_KEY:
        existing_owners = receive_owner_ids(receive)
        if partner_roster_id and owner_id and owner_id != str(partner_roster_id):
            return PackageMutation(
                False,
                "Selected trade partner does not own that asset.",
                send,
                receive,
            )
        if existing_owners and owner_id and owner_id not in existing_owners:
            return PackageMutation(
                False,
                "Receive assets must come from one partner team at a time.",
                send,
                receive,
            )
        if partner_roster_id and not owner_id:
            return PackageMutation(
                False,
                "Ownership for that asset could not be verified for the selected partner.",
                send,
                receive,
            )
    elif package_key == SEND_KEY and my_roster_id and owner_id and owner_id != str(my_roster_id):
        return PackageMutation(False, "You can only send assets on your roster.", send, receive)

    target.append(payload)
    return PackageMutation(
        True,
        "",
        send,
        receive,
        added_label=label,
        invalidate_result=True,
    )


def try_remove_asset(
    *,
    package_key: str,
    index: int,
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
) -> PackageMutation:
    send = _copy_package(send_assets)
    receive = _copy_package(receive_assets)
    target = receive if package_key == RECEIVE_KEY else send
    if index < 0 or index >= len(target):
        return PackageMutation(False, "That asset is no longer in the package.", send, receive)
    target.pop(index)
    return PackageMutation(True, "", send, receive, invalidate_result=True)


def chip_html(asset: Mapping[str, Any], *, format_score=None) -> str:
    from modules.compact_fantasy_assets import compact_asset_html

    inner = compact_asset_html(asset, size="compact", show_value=True, format_score=format_score)
    return f"<div class='toa-chip'>{inner}</div>"


def result_row_html(asset: Mapping[str, Any], *, selected: bool = False) -> str:
    from modules.compact_fantasy_assets import compact_asset_html

    inner = compact_asset_html(asset, size="standard", show_value=False)
    state = " toa-result-row--selected" if selected else ""
    flag = "1" if selected else "0"
    return (
        f"<div class='toa-result-row{state}' data-toa-selected='{flag}'>{inner}</div>"
    )


def apply_mutation(state: MutableMapping[str, Any], mutation: PackageMutation) -> None:
    state[SEND_KEY] = mutation.send_assets
    state[RECEIVE_KEY] = mutation.receive_assets
    state["trade_receive_notice"] = mutation.notice
    if mutation.invalidate_result:
        state["trade_analyzer_analyzed_signature"] = ""
    if mutation.ok and mutation.added_label:
        state["trade_analyzer_add_feedback"] = mutation.added_label
    elif mutation.ok:
        state.pop("trade_analyzer_add_feedback", None)
