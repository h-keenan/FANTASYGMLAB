"""Multi-team (3 to 6 teams) trade model: the transfer matrix, its validation,
and the league-level read over per-team verdicts.

A trade of any size is a list of transfers ``{asset, from_roster, to_roster}``
(exactly what Sleeper stores for a completed trade). For a team T,
``outgoing(T)`` is every asset with ``from == T`` and ``incoming(T)`` every
asset with ``to == T``. A two-team trade is the special case of two mirrored
edges, so the existing send/receive Analyzer maps onto it losslessly
(``from_two_team``).

This module is pure (no I/O): validation takes the rosters / pick owners the
caller already loaded, and ``summarize`` takes the per-team verdicts the engine
(``modules.multi_team_trade_engine``) produced. Nothing here is a valuation
model; each team's number comes from the same Analyzer pipeline a two-team
trade uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from modules import trade_value_bands as bands

MIN_TEAMS = 3
MAX_TEAMS = 6
# Total transfers in one request. Six teams moving a dozen assets each is already
# far beyond a real deal; the cap keeps one request's engine work bounded.
MAX_TRANSFERS = 36

ASSET_PLAYER = "player"
ASSET_PICK = "pick"

# Spread (best team_score minus worst) -> how balanced the whole deal reads.
BALANCED_SPREAD = float(bands.ACCEPT)  # no team is clearly ahead of another
TILTED_SPREAD = float(-bands.DECLINE)  # beyond this somebody is clearly being fleeced

ERR_SHAPE = "invalid_transfer"
ERR_EMPTY = "empty_trade"
ERR_TOO_FEW = "too_few_teams"
ERR_TOO_MANY = "too_many_teams"
ERR_TOO_MANY_TRANSFERS = "too_many_transfers"
ERR_SAME_TEAM = "same_team"
ERR_UNKNOWN_ROSTER = "unknown_roster"
ERR_NOT_OWNED = "asset_not_owned"
ERR_DUPLICATE = "asset_moved_twice"
ERR_UNKNOWN_PICK = "unknown_pick"


@dataclass(frozen=True)
class Transfer:
    asset_type: str  # "player" | "pick"
    asset_id: str  # player_id, or pick_id "{season}:{round}:{original_roster_id}"
    from_roster: str
    to_roster: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.asset_type, self.asset_id)

    def to_public(self) -> dict[str, str]:
        return {
            "type": self.asset_type,
            "id": self.asset_id,
            "from_roster_id": self.from_roster,
            "to_roster_id": self.to_roster,
        }


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_transfers(raw: Iterable[Mapping[str, Any]]) -> tuple[list[Transfer], list[dict[str, str]]]:
    """Normalise raw request rows into ``Transfer`` objects. Malformed rows are
    reported (``ERR_SHAPE``), never silently dropped."""

    transfers: list[Transfer] = []
    errors: list[dict[str, str]] = []
    for index, row in enumerate(raw or ()):
        if not isinstance(row, Mapping):
            errors.append({"code": ERR_SHAPE, "message": f"Transfer {index + 1} is not an object."})
            continue
        kind = _text(row.get("type") or row.get("asset_type")).lower()
        asset_id = _text(row.get("id") or row.get("asset_id"))
        src = _text(row.get("from_roster_id"))
        dst = _text(row.get("to_roster_id"))
        if kind not in (ASSET_PLAYER, ASSET_PICK) or not asset_id or not src or not dst:
            errors.append({
                "code": ERR_SHAPE,
                "message": f"Transfer {index + 1} needs type (player or pick), id, from_roster_id and to_roster_id.",
            })
            continue
        transfers.append(Transfer(kind, asset_id, src, dst))
    return transfers, errors


def participants(transfers: Sequence[Transfer]) -> list[str]:
    """Roster ids in first-appearance order (senders before receivers)."""

    seen: dict[str, None] = {}
    for t in transfers:
        seen.setdefault(t.from_roster, None)
        seen.setdefault(t.to_roster, None)
    return list(seen)


def validate_transfers(
    transfers: Sequence[Transfer],
    *,
    roster_players: Mapping[str, Iterable[Any]],
    pick_owners: Mapping[str, str] | None = None,
    min_teams: int = MIN_TEAMS,
    max_teams: int = MAX_TEAMS,
) -> list[dict[str, str]]:
    """Structural and ownership problems with a transfer matrix (empty = valid).

    ``roster_players`` maps every roster id in the league to its player ids.
    ``pick_owners`` maps ``pick_id`` to the CURRENT owner roster id; leave it
    ``None`` to skip pick ownership (the caller then validates picks itself).

    Rules: at least one transfer; ``min_teams``..``max_teams`` distinct
    participants; no self-transfer; every participant is in the league; every
    asset is owned by its ``from_roster``; no asset moves twice."""

    errors: list[dict[str, str]] = []
    if not transfers:
        return [{"code": ERR_EMPTY, "message": "Add at least one asset to the trade."}]
    if len(transfers) > MAX_TRANSFERS:
        errors.append({
            "code": ERR_TOO_MANY_TRANSFERS,
            "message": f"A trade can move at most {MAX_TRANSFERS} assets.",
        })
    players_by_roster = {
        str(rid): {str(p) for p in (players or ()) if p is not None} for rid, players in roster_players.items()
    }
    seen: set[tuple[str, str]] = set()
    for t in transfers:
        if t.from_roster == t.to_roster:
            errors.append({
                "code": ERR_SAME_TEAM, "asset_id": t.asset_id, "roster_id": t.from_roster,
                "message": "An asset cannot be sent to the team that already owns it.",
            })
        for rid in (t.from_roster, t.to_roster):
            if rid not in players_by_roster:
                errors.append({
                    "code": ERR_UNKNOWN_ROSTER, "roster_id": rid,
                    "message": f"Team {rid} is not in this league.",
                })
        if t.key in seen:
            errors.append({
                "code": ERR_DUPLICATE, "asset_id": t.asset_id,
                "message": "An asset can only move once in a trade.",
            })
        seen.add(t.key)
        if t.from_roster not in players_by_roster:
            continue
        if t.asset_type == ASSET_PLAYER:
            if t.asset_id not in players_by_roster[t.from_roster]:
                errors.append({
                    "code": ERR_NOT_OWNED, "asset_id": t.asset_id, "roster_id": t.from_roster,
                    "message": f"Player {t.asset_id} is not on team {t.from_roster}'s roster.",
                })
        elif pick_owners is not None:
            owner = pick_owners.get(t.asset_id)
            if owner is None:
                errors.append({
                    "code": ERR_UNKNOWN_PICK, "asset_id": t.asset_id,
                    "message": f"Pick {t.asset_id} is not a pick in this league.",
                })
            elif str(owner) != t.from_roster:
                errors.append({
                    "code": ERR_NOT_OWNED, "asset_id": t.asset_id, "roster_id": t.from_roster,
                    "message": f"Pick {t.asset_id} is not owned by team {t.from_roster}.",
                })
    teams = participants(transfers)
    if len(teams) < min_teams:
        errors.append({
            "code": ERR_TOO_FEW,
            "message": f"A multi-team trade needs at least {min_teams} teams (got {len(teams)}).",
        })
    if len(teams) > max_teams:
        errors.append({
            "code": ERR_TOO_MANY,
            "message": f"A trade can include at most {max_teams} teams (got {len(teams)}).",
        })
    return errors


def outgoing(transfers: Sequence[Transfer], roster_id: str) -> list[Transfer]:
    return [t for t in transfers if t.from_roster == str(roster_id)]


def incoming(transfers: Sequence[Transfer], roster_id: str) -> list[Transfer]:
    return [t for t in transfers if t.to_roster == str(roster_id)]


def from_two_team(
    my_roster_id: str,
    partner_roster_id: str,
    *,
    send_player_ids: Sequence[str] = (),
    receive_player_ids: Sequence[str] = (),
    send_pick_ids: Sequence[str] = (),
    receive_pick_ids: Sequence[str] = (),
) -> list[Transfer]:
    """Legacy send/receive request -> the equivalent two mirrored edges."""

    me, them = str(my_roster_id), str(partner_roster_id)
    out = [Transfer(ASSET_PLAYER, str(p), me, them) for p in send_player_ids]
    out += [Transfer(ASSET_PICK, str(p), me, them) for p in send_pick_ids]
    out += [Transfer(ASSET_PLAYER, str(p), them, me) for p in receive_player_ids]
    out += [Transfer(ASSET_PICK, str(p), them, me) for p in receive_pick_ids]
    return out


def to_two_team(transfers: Sequence[Transfer], my_roster_id: str) -> dict[str, list[str]] | None:
    """Inverse of ``from_two_team``; ``None`` unless exactly two teams, one of
    them ``my_roster_id``."""

    teams = participants(transfers)
    me = str(my_roster_id)
    if len(teams) != 2 or me not in teams:
        return None
    return {
        "send_player_ids": [t.asset_id for t in transfers if t.from_roster == me and t.asset_type == ASSET_PLAYER],
        "receive_player_ids": [t.asset_id for t in transfers if t.to_roster == me and t.asset_type == ASSET_PLAYER],
        "send_pick_ids": [t.asset_id for t in transfers if t.from_roster == me and t.asset_type == ASSET_PICK],
        "receive_pick_ids": [t.asset_id for t in transfers if t.to_roster == me and t.asset_type == ASSET_PICK],
    }


# ---------------------------------------------------------------------------
# League-level read
# ---------------------------------------------------------------------------

OUTCOME_BY_TONE = {"accept": "wins", "fair": "even", "counter": "gives_up", "decline": "loses"}


def outcome_for_tone(tone: str) -> str:
    return OUTCOME_BY_TONE.get(str(tone or "fair"), "even")


def balance_for_spread(spread: float) -> tuple[str, str]:
    """(id, label) for how evenly the deal treats its teams."""

    if spread < BALANCED_SPREAD:
        return "balanced", "Balanced: no team is clearly ahead"
    if spread < TILTED_SPREAD:
        return "tilted", "Tilted: one team comes out clearly ahead"
    return "lopsided", "Lopsided: at least one team is giving up a lot"


def summarize(teams: Sequence[Mapping[str, Any]], perspective_roster_id: str = "") -> dict[str, Any]:
    """League-level read from per-team results.

    Each ``teams`` row carries ``roster_id``, ``team_name``, ``trade_score``
    (the Analyzer's posture- and lineup-aware score for THAT team), ``market_delta``
    and ``outcome``. Scores are never averaged: the headline is the worst team
    (most hurt), the best team, and the spread between them."""

    if not teams:
        return {}
    ranked = sorted(teams, key=lambda t: (float(t["trade_score"]), float(t["market_delta"])), reverse=True)
    best, worst = ranked[0], ranked[-1]
    spread = float(best["trade_score"]) - float(worst["trade_score"])
    balance_id, balance_label = balance_for_spread(spread)
    outcomes: dict[str, list[str]] = {"wins": [], "even": [], "gives_up": [], "loses": []}
    for t in teams:
        outcomes.setdefault(str(t.get("outcome") or "even"), []).append(str(t["roster_id"]))
    worst_name = str(worst.get("team_name") or f"Team {worst['roster_id']}")
    best_name = str(best.get("team_name") or f"Team {best['roster_id']}")
    if balance_id == "balanced":
        headline = "Every team comes out in a reasonable place."
    elif float(worst["trade_score"]) > bands.COUNTER:
        headline = f"{best_name} comes out ahead, but no team is hurt badly."
    else:
        headline = f"{worst_name} is the team most hurt by this deal; {best_name} comes out ahead."
    market_sum = sum(float(t["market_delta"]) for t in teams)
    perspective = next((t for t in teams if str(t["roster_id"]) == str(perspective_roster_id)), None)
    return {
        "team_count": len(teams),
        "headline": headline,
        "balance": {
            "id": balance_id,
            "label": balance_label,
            "spread": round(spread),
            "best_roster_id": str(best["roster_id"]),
            "worst_roster_id": str(worst["roster_id"]),
        },
        "most_hurt_roster_id": str(worst["roster_id"]),
        "best_off_roster_id": str(best["roster_id"]),
        "outcomes": outcomes,
        "ranking": [
            {"rank": i + 1, "roster_id": str(t["roster_id"]), "team_name": t.get("team_name"),
             "trade_score": round(float(t["trade_score"]))}
            for i, t in enumerate(ranked)
        ],
        # Market value is zero-sum across a closed trade; a large number here
        # means a price was missing and is shown so clients can say so.
        "market_sum": round(market_sum),
        "perspective": (
            {
                "roster_id": str(perspective["roster_id"]),
                "outcome": perspective.get("outcome"),
                "rank": next(i + 1 for i, t in enumerate(ranked) if t is perspective),
                "of": len(ranked),
            }
            if perspective is not None
            else None
        ),
    }
