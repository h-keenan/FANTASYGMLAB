"""Canonical compact fantasy-asset presentation (player + pick).

Presentation only. Callers supply already-known identity/value fields.
HTML surfaces use the existing Sleeper CDN URL helper — never a sync byte fetch.
"""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

from modules.football_assets import player_name_html
from modules.player_images import get_player_image_url
from modules.player_profile_ui import avatar_html


MAX_SIDE_ASSETS = 3

COMPACT_FANTASY_ASSET_CSS = """
.dg-compact-asset{align-items:center;box-sizing:border-box;column-gap:var(--space-xs);display:grid;grid-template-columns:var(--size-asset-compact) minmax(0,1fr) max-content;justify-content:start;max-width:100%;min-width:0;width:max-content}
.dg-compact-asset--chip{column-gap:var(--space-2xs);grid-template-columns:var(--size-asset-chip) minmax(0,1fr)}
.dg-compact-asset--standard{grid-template-columns:var(--size-asset-standard) minmax(0,1fr) max-content}
.dg-compact-asset-avatar,.dg-compact-pick-plate{align-items:center;background:var(--color-surface-muted);border:var(--border-width-default) solid var(--color-border);box-sizing:border-box;display:inline-flex;flex:0 0 var(--size-asset-compact);height:var(--size-asset-compact);justify-content:center;margin:0;overflow:hidden;padding:0;width:var(--size-asset-compact)}
.dg-compact-asset--chip .dg-compact-asset-avatar,.dg-compact-asset--chip .dg-compact-pick-plate{flex-basis:var(--size-asset-chip);height:var(--size-asset-chip);width:var(--size-asset-chip)}
.dg-compact-asset--standard .dg-compact-asset-avatar,.dg-compact-asset--standard .dg-compact-pick-plate{flex-basis:var(--size-asset-standard);height:var(--size-asset-standard);width:var(--size-asset-standard)}
.dg-compact-asset-avatar .dg-player-headshot-image,.dg-compact-asset-avatar img{height:100%;object-fit:contain;width:100%;z-index:1}
.dg-compact-asset-avatar .dg-player-headshot-fallback{color:var(--color-text-secondary);font-size:var(--font-size-badge);font-weight:var(--font-weight-title);z-index:0}
.dg-compact-asset-avatar:has(img.dg-player-headshot-image) .dg-player-headshot-fallback,
.dg-compact-asset-avatar:has(.dg-player-headshot-image.is-loaded) .dg-player-headshot-fallback{opacity:0;visibility:hidden}
.dg-compact-pick-plate{color:var(--color-information);flex-direction:column;font-size:var(--font-size-badge);font-weight:var(--font-weight-title);letter-spacing:var(--letter-spacing-badge);line-height:1.05;text-align:center;text-transform:uppercase}
.dg-compact-asset-copy{align-content:center;display:grid;gap:0;justify-items:start;margin:0;min-width:0;padding:0;text-align:left}
.dg-compact-asset-name,.toa-chip-name{color:var(--color-text-primary);font:var(--font-card-title);line-height:1.15;margin:0;overflow-wrap:break-word;padding:0;text-align:left;word-break:normal}
.dg-compact-asset-meta,.toa-chip-meta{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);line-height:1.2;margin:0;padding:0;text-align:left}
.dg-compact-asset-role{color:var(--color-text-secondary);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);line-height:1.2;margin:0;padding:0;text-align:left}
.dg-compact-asset-value,.toa-chip-value{align-self:center;color:var(--color-text-secondary);font-variant-numeric:tabular-nums;font:var(--type-supporting-metadata);justify-self:end;white-space:nowrap}
.dg-compact-asset-stack{display:flex;flex-direction:column;gap:var(--space-2xs);max-width:100%;min-width:0;width:max-content}
.dg-compact-asset-sep{align-items:center;color:var(--color-information);display:flex;font:var(--type-supporting-metadata);justify-content:center;letter-spacing:var(--letter-spacing-badge);line-height:1;min-height:1rem;pointer-events:none}
.dg-trade-matchup{align-items:stretch;display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr);max-width:42rem;min-width:0}
.dg-trade-matchup-vs{align-items:center;color:var(--color-information);display:none;font:var(--type-supporting-metadata);justify-content:center;letter-spacing:var(--letter-spacing-badge)}
.dg-trade-side{background:var(--color-surface-muted);min-width:0;padding:var(--space-xs) var(--space-sm)}
.dg-trade-side-label{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:0 0 var(--space-2xs);text-transform:uppercase}
.dg-gp-identity-row{align-items:center;display:flex;flex-wrap:wrap;gap:var(--space-xs);max-width:40rem;min-width:0}
.dg-gp-watch-list{display:flex;flex-direction:column;gap:var(--space-xs);justify-content:start;max-width:40rem;min-width:0;width:max-content}
.dg-gp-trade-visual{align-items:stretch;display:grid;gap:var(--space-xs);grid-template-columns:minmax(0,1fr);justify-content:start;max-width:40rem;min-width:0;width:max-content}
.dg-gp-trade-side{display:grid;gap:var(--space-2xs);justify-items:start;min-width:0}
.dg-gp-trade-side-label{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:0;text-transform:uppercase}
.dg-gp-trade-for{align-self:center;color:var(--color-information);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:0;text-align:center;text-transform:uppercase}
.dg-gp-value-edge{color:var(--color-success);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin-top:var(--space-2xs);max-width:40rem}
@media (min-width:700px){
.dg-trade-matchup{align-items:start;grid-template-columns:minmax(0,max-content) 1.5rem minmax(0,max-content);justify-content:start}
.dg-trade-matchup-vs{display:flex}
.dg-gp-trade-visual{align-items:center;column-gap:var(--space-md);grid-template-columns:minmax(0,max-content) auto minmax(0,max-content);justify-content:start}
}
@media (max-width:760px){
.dg-compact-asset:not(.dg-compact-asset--chip){grid-template-columns:var(--size-asset-compact) minmax(0,1fr) max-content;width:100%}
.dg-gp-trade-visual{grid-template-columns:minmax(0,1fr)}
.dg-gp-trade-for{justify-self:start;text-align:left}
}
"""


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _initials(name: str) -> str:
    parts = [part for part in _text(name).split() if part]
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    if parts:
        return parts[0][:2].upper()
    return "?"


def _format_value(raw: object) -> str:
    if raw in (None, ""):
        return ""
    if isinstance(raw, str) and not raw.replace(",", "").replace(".", "").replace("-", "").isdigit():
        return raw.strip()
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return _text(raw)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.1f}"


def presentation_asset(asset: Mapping[str, Any] | None) -> dict[str, Any]:
    """Small serializable view-model. No dataframes, no provider calls."""

    if not isinstance(asset, Mapping):
        return {}
    kind = _text(asset.get("asset_type"), "player").lower()
    if kind == "pick":
        season = _text(asset.get("season"))
        round_no = _text(asset.get("round"))
        label = _text(asset.get("label") or asset.get("name"))
        if not label and season and round_no:
            label = f"{season} Round {round_no}"
        return {
            "asset_type": "pick",
            "label": label or "Draft pick",
            "season": season,
            "round": round_no,
            "score": asset.get("score", asset.get("value_score")),
            "owner_team_name": _text(asset.get("owner_team_name")),
        }
    name = _text(asset.get("name") or asset.get("label"), "Player")
    role = _text(asset.get("opportunity_label") or asset.get("role") or asset.get("roster_relevance"))
    if role and role.islower():
        role = role.replace("_", " ").title()
    return {
        "asset_type": "player",
        "player_id": _text(asset.get("player_id")),
        "name": name,
        "position": _text(asset.get("position")).upper(),
        "team": _text(asset.get("team")).upper(),
        "age": asset.get("age"),
        "score": asset.get("score", asset.get("value_score")),
        "role": role,
        "injury_status": _text(asset.get("injury_status")),
    }


def compact_package(
    send_assets: Sequence[Mapping[str, Any]] | None,
    receive_assets: Sequence[Mapping[str, Any]] | None,
    *,
    value_edge: str = "",
    max_per_side: int = MAX_SIDE_ASSETS,
) -> dict[str, Any]:
    send = [
        presentation_asset(asset)
        for asset in (send_assets or [])
        if isinstance(asset, Mapping)
    ][:max_per_side]
    receive = [
        presentation_asset(asset)
        for asset in (receive_assets or [])
        if isinstance(asset, Mapping)
    ][:max_per_side]
    return {
        "send": [item for item in send if item],
        "receive": [item for item in receive if item],
        "value_edge": _text(value_edge),
    }


def compact_player_chip(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {}
    payload = presentation_asset(
        {
            "asset_type": "player",
            "player_id": row.get("player_id"),
            "name": row.get("name") or row.get("label"),
            "position": row.get("position"),
            "team": row.get("team"),
            "age": row.get("age"),
            "score": row.get("score", row.get("value_score")),
            "opportunity_label": row.get("opportunity_label") or row.get("role"),
            "roster_relevance": row.get("roster_relevance"),
            "injury_status": row.get("injury_status"),
        }
    )
    return payload


def compact_asset_html(
    asset: Mapping[str, Any] | None,
    *,
    size: str = "compact",
    show_value: bool = True,
    format_score=None,
) -> str:
    payload = presentation_asset(asset)
    if not payload:
        return ""
    size_class = {
        "chip": "dg-compact-asset--chip",
        "standard": "dg-compact-asset--standard",
        "compact": "",
    }.get(size, "")
    classes = "dg-compact-asset"
    if size_class:
        classes += f" {size_class}"
    value_raw = payload.get("score")
    value = ""
    if show_value and value_raw not in (None, ""):
        if format_score is not None:
            try:
                value = str(format_score(value_raw))
            except Exception:
                value = _format_value(value_raw)
        else:
            value = _format_value(value_raw)
    value_html = (
        f"<div class='dg-compact-asset-value toa-chip-value'>{escape(value)}</div>"
        if value
        else ""
    )
    if payload.get("asset_type") == "pick":
        classes += " dg-compact-asset--pick"
        season = _text(payload.get("season"))
        round_no = _text(payload.get("round"))
        plate_bits = ["PICK"]
        if season:
            plate_bits.append(season[-2:] if len(season) >= 4 else season)
        plate = "<br>".join(escape(bit) for bit in plate_bits[:2])
        name = _text(payload.get("label"), "Draft pick")
        meta_bits = []
        if season and round_no:
            expected = f"{season} Round {round_no}"
            if expected.casefold() not in name.casefold() and f"round {round_no}".casefold() not in name.casefold():
                meta_bits.append(expected)
        owner = _text(payload.get("owner_team_name"))
        if owner:
            meta_bits.append(owner)
        meta_html = (
            f"<div class='dg-compact-asset-meta toa-chip-meta'>{escape(' · '.join(meta_bits))}</div>"
            if meta_bits
            else ""
        )
        return (
            f"<div class='{classes}'>"
            f"<div class='dg-compact-pick-plate' aria-hidden='true'>{plate}</div>"
            "<div class='dg-compact-asset-copy toa-chip-copy'>"
            f"<div class='dg-compact-asset-name toa-chip-name'>{escape(name)}</div>"
            f"{meta_html}"
            "</div>"
            f"{value_html}"
            "</div>"
        )

    classes += " dg-compact-asset--player"
    name = _text(payload.get("name"), "Player")
    player_id = _text(payload.get("player_id"))
    image_url = get_player_image_url(player_id) if player_id else ""
    avatar_class = "dg-compact-asset-avatar"
    if size == "chip":
        avatar_class += " dg-compact-asset-avatar--chip"
    avatar = avatar_html(image_url, _initials(name), css_class=avatar_class)
    identity_bits = [
        bit
        for bit in (
            _text(payload.get("position")).upper(),
            _text(payload.get("team")).upper(),
        )
        if bit
    ]
    age = payload.get("age")
    if size != "chip" and age not in (None, ""):
        try:
            identity_bits.append(f"Age {int(float(age))}")
        except (TypeError, ValueError):
            pass
    meta = " · ".join(identity_bits) if identity_bits else "Player"
    role = _text(payload.get("role"))
    if size == "chip" and role:
        meta = role if not identity_bits else f"{meta} · {role}"
    extras: list[str] = []
    if size != "chip" and role:
        extras.append(role)
    injury_status = _text(payload.get("injury_status"))
    if (
        size != "chip"
        and injury_status
        and injury_status.casefold() not in {"active", "healthy", "na", "none"}
    ):
        extras.append(injury_status)
    extra_html = (
        f"<div class='dg-compact-asset-role'>{escape(' · '.join(extras))}</div>"
        if extras
        else ""
    )
    return (
        f"<div class='{classes}'>"
        f"{avatar}"
        "<div class='dg-compact-asset-copy toa-chip-copy'>"
        f"<div class='dg-compact-asset-name toa-chip-name'>{player_name_html(name)}</div>"
        f"<div class='dg-compact-asset-meta toa-chip-meta'>{escape(meta)}</div>"
        f"{extra_html}"
        "</div>"
        f"{value_html}"
        "</div>"
    )


def compact_asset_stack_html(
    assets: Sequence[Mapping[str, Any]] | None,
    *,
    size: str = "compact",
    show_value: bool = True,
    format_score=None,
) -> str:
    rows = [
        compact_asset_html(asset, size=size, show_value=show_value, format_score=format_score)
        for asset in (assets or [])
        if isinstance(asset, Mapping)
    ]
    rows = [row for row in rows if row]
    if not rows:
        return "<div class='dg-compact-asset-stack'><div class='dg-compact-asset-meta'>None selected</div></div>"
    parts: list[str] = []
    for index, row in enumerate(rows):
        if index:
            parts.append("<div class='dg-compact-asset-sep' aria-hidden='true'>+</div>")
        parts.append(row)
    return f"<div class='dg-compact-asset-stack'>{''.join(parts)}</div>"


def compact_matchup_html(
    send_assets: Sequence[Mapping[str, Any]] | None,
    receive_assets: Sequence[Mapping[str, Any]] | None,
    *,
    send_label: str = "You send",
    receive_label: str = "You receive",
    size: str = "compact",
    show_value: bool = True,
    format_score=None,
) -> str:
    return (
        "<div class='dg-trade-matchup'>"
        "<div class='dg-trade-side dg-trade-side--receive toa-side toa-side-receive'>"
        f"<div class='dg-trade-side-label toa-side-label'>{escape(receive_label)}</div>"
        f"{compact_asset_stack_html(receive_assets, size=size, show_value=show_value, format_score=format_score)}"
        "</div>"
        "<div class='dg-trade-matchup-vs' aria-hidden='true'>↔</div>"
        "<div class='dg-trade-side dg-trade-side--send toa-side toa-side-send'>"
        f"<div class='dg-trade-side-label toa-side-label'>{escape(send_label)}</div>"
        f"{compact_asset_stack_html(send_assets, size=size, show_value=show_value, format_score=format_score)}"
        "</div>"
        "</div>"
    )


def identity_chips_html(
    players: Sequence[Mapping[str, Any]] | None,
    *,
    size: str = "chip",
) -> str:
    chips = [
        compact_asset_html(player, size=size, show_value=False)
        for player in (players or [])
        if isinstance(player, Mapping)
    ]
    chips = [chip for chip in chips if chip]
    if not chips:
        return ""
    return f"<div class='dg-gp-identity-row'>{''.join(chips)}</div>"


def watch_attention_html(players: Sequence[Mapping[str, Any]] | None) -> str:
    """Compact attention rows — portraits + identity, not debug pipes."""

    rows = [
        compact_asset_html(player, size="compact", show_value=False)
        for player in (players or [])
        if isinstance(player, Mapping)
    ]
    rows = [row for row in rows if row]
    if not rows:
        return ""
    return f"<div class='dg-gp-watch-list' data-gp-watch='1'>{''.join(rows)}</div>"


def game_plan_trade_visual_html(presentation: Mapping[str, Any] | None) -> str:
    if not isinstance(presentation, Mapping):
        return ""
    send = presentation.get("send") or []
    receive = presentation.get("receive") or []
    if not send and not receive:
        return ""
    edge = _text(presentation.get("value_edge"))
    if edge and "value edge" not in edge.casefold():
        edge_label = f"{edge} VALUE EDGE"
    else:
        edge_label = edge
    edge_html = (
        f"<div class='dg-gp-value-edge'>{escape(edge_label)}</div>" if edge_label else ""
    )
    return (
        "<div class='dg-gp-trade-visual' data-gp-trade-visual='1'>"
        "<div class='dg-gp-trade-side dg-gp-trade-side--give'>"
        "<div class='dg-gp-trade-side-label'>You give</div>"
        f"{compact_asset_stack_html(send, size='compact', show_value=False)}"
        "</div>"
        "<div class='dg-gp-trade-for'>FOR</div>"
        "<div class='dg-gp-trade-side dg-gp-trade-side--get'>"
        "<div class='dg-gp-trade-side-label'>You get</div>"
        f"{compact_asset_stack_html(receive, size='compact', show_value=False)}"
        "</div>"
        "</div>"
        f"{edge_html}"
    )
