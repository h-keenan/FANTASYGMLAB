"""IDP rows for My Team and Waivers, adapted from ``modules.idp_league_values``.

Only what the IDP model already computed is surfaced: the model value (as
``score``), team, age and injury. Tier, OVR, ranks and trend are left empty
(``None``) rather than invented, so clients hide them. Non-IDP leagues
(``idp: False``) always produce no rows.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from modules import idp_scoring


def _lineup_row(pid: Any, name: Any, family: Any, team: Any, age: Any, injury: Any, value: Any) -> Dict[str, Any]:
    injury_text = str(injury or "").strip()
    return {
        "player_id": str(pid),
        "name": name,
        "position": family,
        "team": team,
        "age": age,
        "status": "Active",
        "injury_status": injury or None,
        "injury_label": injury_text.title() if injury_text else "",
        "ruled_out": False,
        "tier": None,
        "score": value,
        "slot": None,
        "suggested_starter": False,
        "roster_slot": "bench",
        "opportunity_label": None,
        "overall_rating": None,
    }


# The IDP engine's own evidence grade (modules.idp_values): "high" is 20+
# defensive games of history. Anything thinner is a model guess that Trade Hub
# and counter-offer suggestions must not build ideas around.
TRUSTED_CONFIDENCE = "high"


def trusted_idp_ids(result: Mapping[str, Any]) -> set[str]:
    """Defenders whose model value is backed by enough games to act on."""

    if not result.get("idp"):
        return set()
    return {
        str(entry["player_id"])
        for entry in result.get("players") or []
        if entry.get("confidence") == TRUSTED_CONFIDENCE and entry.get("value")
    }


def all_idp_ids(result: Mapping[str, Any]) -> set[str]:
    if not result.get("idp"):
        return set()
    return {str(e["player_id"]) for e in result.get("players") or []} | {
        str(e["player_id"]) for e in result.get("below_replacement_players") or []
    }


def trade_pool_rows(result: Mapping[str, Any], wanted_below_ids: Any = ()) -> List[Dict[str, Any]]:
    """Defenders as trade-asset rows. Valued defenders keep their model value;
    a below-replacement defender is included only when asked for (a roster
    member or a chosen asset) and carries ``value: None`` (shown as a dash)."""

    if not result.get("idp"):
        return []
    wanted = {str(pid) for pid in (wanted_below_ids or ())}
    rows = [dict(entry) for entry in result.get("players") or []]
    rows += [dict(e) for e in result.get("below_replacement_players") or [] if str(e["player_id"]) in wanted]
    return rows


def roster_idp_rows(
    result: Mapping[str, Any],
    roster_player_ids: Any,
    players_lookup: Mapping[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Rostered defenders as My Team rows, best model value first.

    A rostered defender projected below this league's replacement level is
    still listed (so he does not vanish from the roster) with ``score: None``.
    """

    if not result.get("idp"):
        return []
    ids = {str(pid) for pid in (roster_player_ids or ()) if pid}
    rows: List[Dict[str, Any]] = []
    for entry in result.get("players") or []:
        if str(entry["player_id"]) in ids:
            rows.append(
                _lineup_row(
                    entry["player_id"], entry["name"], entry["family"], entry.get("team"),
                    entry.get("age"), entry.get("injury_status"), entry["value"],
                )
            )
    seen = {row["player_id"] for row in rows}
    for pid in result.get("below_replacement_ids") or []:
        pid = str(pid)
        if pid not in ids or pid in seen:
            continue
        info = (players_lookup or {}).get(pid) or {}
        family = idp_scoring.idp_slot_family(info.get("position"))
        name = info.get("full_name") or " ".join(str(info.get(k) or "") for k in ("first_name", "last_name")).strip()
        if not family or not name:
            continue
        rows.append(_lineup_row(pid, name, family, info.get("team"), info.get("age"), info.get("injury_status"), None))
    return rows


def free_agent_idp_rows(result: Mapping[str, Any], rostered_ids: Any, limit: int = 100) -> List[Dict[str, Any]]:
    """Unrostered defenders as Waivers rows (WaiverPlayer-shaped), best first."""

    if not result.get("idp"):
        return []
    taken = {str(pid) for pid in (rostered_ids or ()) if pid}
    rows: List[Dict[str, Any]] = []
    for entry in result.get("players") or []:
        if str(entry["player_id"]) in taken:
            continue
        rows.append(
            {
                "player_id": str(entry["player_id"]),
                "name": entry["name"],
                "position": entry["family"],
                "team": entry.get("team"),
                "age": entry.get("age"),
                "status": "Active",
                "injury_status": entry.get("injury_status"),
                "tier": None,
                "opportunity_label": None,
                "score": entry["value"],
                "position_rank": None,
                "overall_rank": None,
                "stale_free_agent": False,
                "injury_replacement_fit": False,
                "injury_replacement_note": "",
                "sleeper_trending_add": False,
                "sleeper_trending_add_count": None,
                "sleeper_trending_add_rank": None,
                "opponent": None,
                "opponent_is_home": None,
                "opponent_defense_tier": None,
                "overall_rating": None,
            }
        )
        if len(rows) >= limit:
            break
    return rows
