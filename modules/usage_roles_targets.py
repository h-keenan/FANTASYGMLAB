"""Rising / shrinking player roles as a bounded trade-idea nudge (handshake 10, part 2).

``usage_trends`` flags a corroborated ``role_expanding`` / ``role_shrinking`` (two
independent usage metrics moving together plus a points read). This module turns
those flags into a SMALL preference inside the existing market-realism score:

* a target with a growing role is slightly preferred, when another real factor
  agrees (he fills one of my needs, or my posture wants him);
* a player I send with a shrinking role is slightly preferred, when another real
  factor agrees (I am contending or rebuilding, i.e. selling, or the position is
  not a need of mine).

Guardrails (constants below, all tested):

* The nudge is at most ``MAX_POINTS`` of the 0-100 realism score.
* It shares the partner-context budget: ``trade_ideas`` applies
  ``clamp(partner_points + roles_points, +/-partner_context.COMBINED_MAX_POINTS)``,
  so the combined shift can never exceed the existing +/-6.
* It never enters ``partner_acceptance_context``: the partner loss cap, the
  lopsided verdict and the hard ceiling are untouched, and no pick or player is
  repriced. A single flag alone is never enough (two factors required).
* Role flags are Pro data (``usage_trends`` Pro gate): the caller passes a role
  map only for a Pro caller, in season. No map, no nudge.

Kill switch: ``DYNASTYGM_USAGE_ROLES_TARGETS_V1`` (default ON; 0/false/off restores
the previous output exactly)."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from modules import experimental_graduation

ENV_KEY = "DYNASTYGM_USAGE_ROLES_TARGETS_V1"
TARGET_POINTS = 1.5
SEND_POINTS = 1.5
MAX_POINTS = 2.0
ROLE_KEYS = ("role_expanding", "role_shrinking")
SELL_POSTURES = {"contender", "fringe_contender", "rebuild", "tank"}


def enabled() -> bool:
    return experimental_graduation.graduated_kill_switch_enabled(ENV_KEY, default=True)


def fingerprint_token(pro: bool) -> str:
    """Cache-key part: the flag and the gate (Free callers never see the nudge)."""

    return f"ur={int(enabled() and bool(pro))}"


def role_map(
    players: Iterable[tuple[Any, str]], season_stats: Mapping[str, Any] | None
) -> dict[str, dict[str, str]]:
    """``player_id -> {"key", "explanation"}`` for corroborated role flags only."""

    from modules import usage_trends

    out: dict[str, dict[str, str]] = {}
    for pid, position in players:
        pos = str(position or "").upper()
        if pos not in usage_trends.COVERED_POSITIONS:
            continue
        profile = usage_trends.profile_from_season_stats(pid, pos, season_stats)
        for flag in (profile or {}).get("flags") or ():
            if flag.get("key") in ROLE_KEYS and flag.get("explanation"):
                out[str(pid)] = {"key": flag["key"], "explanation": str(flag["explanation"])}
                break
    return out


def _short_name(label: Any) -> str:
    parts = str(label or "").split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else str(label or "")


def _line(asset: Mapping[str, Any], flag: Mapping[str, str]) -> str:
    text = str(flag["explanation"])
    for lead, word in (("His role is growing", "growing"), ("His role is shrinking", "shrinking")):
        if text.startswith(lead):
            who = _short_name(asset.get("label") or asset.get("name"))
            text = f"{who}'s role is {word}" + text[len(lead):]
            break
    # One short clause: the lead evidence metric, not the points read.
    return text.split(". PPR")[0].split("; ")[0].rstrip(".")


def _players(assets: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [a for a in assets if a.get("asset_type") == "player"]


def _age(asset: Mapping[str, Any]) -> float:
    try:
        return float(asset.get("age") or 0)
    except (TypeError, ValueError):
        return 0.0


def adjustment(
    *,
    roles: Mapping[str, Mapping[str, str]] | None,
    my_strategy: str,
    my_needs: Iterable[str],
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """``send_assets`` is what the USER sends; ``receive_assets`` is what they get."""

    empty: dict[str, Any] = {"points": 0.0, "lines": []}
    if not roles or not enabled():
        return empty
    needs = {str(p).upper() for p in my_needs or ()}
    strategy = str(my_strategy or "").lower()
    points = 0.0
    lines: list[str] = []
    for asset in _players(receive_assets):
        flag = roles.get(str(asset.get("player_id") or ""))
        if not flag or flag["key"] != "role_expanding":
            continue
        fills = str(asset.get("position") or "").upper() in needs
        wants = strategy in {"contender", "fringe_contender"} or (
            strategy in {"rebuild", "tank"} and 0 < _age(asset) <= 25
        )
        if fills or wants:  # the flag plus one more real factor
            points += TARGET_POINTS * (1.0 if fills and wants else 0.75)
            lines.append(_line(asset, flag))
    for asset in _players(send_assets):
        flag = roles.get(str(asset.get("player_id") or ""))
        if not flag or flag["key"] != "role_shrinking":
            continue
        selling = strategy in SELL_POSTURES
        spare = str(asset.get("position") or "").upper() not in needs
        if selling or spare:
            points += SEND_POINTS * (1.0 if selling and spare else 0.75)
            lines.append(_line(asset, flag))
    return {"points": round(min(points, MAX_POINTS), 2), "lines": lines[:2]}
