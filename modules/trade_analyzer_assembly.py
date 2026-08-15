"""Trade Analyzer construction catalogs, filters, and matchup remap.

Presentation/state only. Does not run valuation, recommendations, or providers.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence

from modules import trade_analyzer_builder as analyzer_builder


KIND_PLAYERS = "Players"
KIND_PICKS = "Picks"
KIND_OPTIONS = (KIND_PLAYERS, KIND_PICKS)
POSITION_OPTIONS = ("ALL", "QB", "RB", "WR", "TE", "K")

SEND_KEY = analyzer_builder.SEND_KEY
RECEIVE_KEY = analyzer_builder.RECEIVE_KEY

CATALOG_CONTEXT_KEY = "toa_catalog_key"
CATALOG_PLAYERS_ME = "toa_catalog_players_me"
CATALOG_PICKS_ME = "toa_catalog_picks_me"
CATALOG_PLAYERS_PARTNER = "toa_catalog_players_partner"
CATALOG_PICKS_PARTNER = "toa_catalog_picks_partner"
MATCHUP_KEY = "toa_last_matchup_key"

ASSEMBLY_STATE_KEYS: tuple[str, ...] = (
    CATALOG_CONTEXT_KEY,
    CATALOG_PLAYERS_ME,
    CATALOG_PICKS_ME,
    CATALOG_PLAYERS_PARTNER,
    CATALOG_PICKS_PARTNER,
    MATCHUP_KEY,
    "toa_receive_kind",
    "toa_send_kind",
    "toa_receive_pos",
    "toa_send_pos",
    "toa_assembly_notice",
)


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _int_score(value: object) -> int:
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def player_asset_from_mapping(
    row: Mapping[str, Any],
    *,
    owner_info: Mapping[str, Any] | None = None,
    score_field: str = "value_score",
) -> dict[str, Any]:
    """Copy already-loaded player identity/value fields into a package asset."""

    info = owner_info or {}
    player_id = _text(row.get("player_id"))
    name = _text(row.get("name") or row.get("label"), "Player")
    score_raw = row.get("score", row.get(score_field, row.get("value_score", 0)))
    return {
        "asset_type": "player",
        "player_id": player_id,
        "name": name,
        "label": name,
        "position": _text(row.get("position")),
        "team": _text(row.get("team")),
        "status": _text(row.get("status")),
        "injury_status": _text(row.get("injury_status")),
        "age": row.get("age"),
        "player_tier": _text(row.get("player_tier")),
        "opportunity_label": _text(row.get("opportunity_label")),
        "opportunity_score": _int_score(row.get("opportunity_score")),
        "opportunity_explanation": _text(row.get("opportunity_explanation")),
        "value_score": _int_score(row.get("value_score")),
        "score": _int_score(score_raw),
        "owner_roster_id": _text(row.get("owner_roster_id") or info.get("owner_roster_id")),
        "owner_team_name": _text(row.get("owner_team_name") or info.get("owner_team_name")),
    }


def pick_asset_from_mapping(
    pick: Mapping[str, Any],
    *,
    pick_score_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Copy already-loaded pick fields; apply the same display multiplier as search."""

    label = _text(pick.get("label") or pick.get("name"), "Draft pick")
    raw = pick.get("score", 0)
    try:
        score = max(0, int(round(float(raw or 0) * float(pick_score_multiplier))))
    except (TypeError, ValueError):
        score = 0
    return {
        "asset_type": "pick",
        "label": label,
        "name": label,
        "value_score": _int_score(pick.get("score", pick.get("value_score", 0))),
        "score": score,
        "season": pick.get("season"),
        "round": pick.get("round"),
        "owner_roster_id": _text(pick.get("owner_roster_id")),
        "owner_team_name": _text(pick.get("owner_team_name")),
        "original_team_name": _text(pick.get("original_team_name")),
    }


def _player_rows_for_ids(players_df, player_ids: Sequence[str]) -> list[Mapping[str, Any]]:
    wanted = {str(pid) for pid in player_ids if pid is not None and str(pid).strip()}
    if not wanted or players_df is None or getattr(players_df, "empty", True):
        return []
    frame = players_df[players_df["player_id"].astype(str).isin(wanted)]
    rows: list[Mapping[str, Any]] = []
    for _, row in frame.iterrows():
        rows.append(row)
    return rows


def build_side_catalog(
    *,
    players_df,
    player_ids: Sequence[str],
    picks: Sequence[Mapping[str, Any]] | None,
    player_owner_map: Mapping[str, Mapping[str, Any]] | None = None,
    pick_score_multiplier: float = 1.0,
    score_field: str = "value_score",
) -> dict[str, list[dict[str, Any]]]:
    owners = player_owner_map or {}
    players: list[dict[str, Any]] = []
    for row in _player_rows_for_ids(players_df, player_ids):
        pid = _text(row.get("player_id"))
        players.append(
            player_asset_from_mapping(
                row,
                owner_info=owners.get(pid, {}),
                score_field=score_field,
            )
        )
    players.sort(key=lambda asset: (-_int_score(asset.get("score")), _text(asset.get("name"))))
    pick_assets = [
        pick_asset_from_mapping(pick, pick_score_multiplier=pick_score_multiplier)
        for pick in (picks or [])
        if isinstance(pick, Mapping)
    ]
    pick_assets.sort(
        key=lambda asset: (
            _int_score(asset.get("season")) or 9999,
            _int_score(asset.get("round")) or 99,
            _text(asset.get("label")),
        )
    )
    return {"players": players, "picks": pick_assets}


def filter_assets(
    catalog: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    *,
    kind: str = KIND_PLAYERS,
    position: str = "ALL",
    query: str = "",
    exclude_identities: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """In-memory roster filter. Never searches the league-wide player universe."""

    bucket = KIND_PICKS if _text(kind) == KIND_PICKS else KIND_PLAYERS
    source = (catalog or {}).get("picks" if bucket == KIND_PICKS else "players") or []
    needle = _text(query).casefold()
    pos = _text(position, "ALL").upper()
    skip = {item for item in (exclude_identities or []) if item}
    filtered: list[dict[str, Any]] = []
    for asset in source:
        if not isinstance(asset, Mapping):
            continue
        identity = analyzer_builder.asset_identity(asset)
        if identity and identity in skip:
            continue
        if bucket == KIND_PLAYERS and pos not in {"", "ALL"}:
            if _text(asset.get("position")).upper() != pos:
                continue
        if needle:
            haystack = " ".join(
                (
                    _text(asset.get("name")),
                    _text(asset.get("label")),
                    _text(asset.get("position")),
                    _text(asset.get("team")),
                    _text(asset.get("season")),
                    _text(asset.get("round")),
                    _text(asset.get("owner_team_name")),
                )
            ).casefold()
            if needle not in haystack:
                continue
        filtered.append(dict(asset))
    return filtered


def assets_owned_by(
    assets: Sequence[Mapping[str, Any]] | None,
    roster_id: str,
) -> list[dict[str, Any]]:
    owner = _text(roster_id)
    if not owner:
        return []
    return [
        dict(asset)
        for asset in (assets or [])
        if isinstance(asset, Mapping) and _text(asset.get("owner_roster_id")) == owner
    ]


def apply_matchup_change(
    state: MutableMapping[str, Any],
    *,
    my_roster_id: str,
    partner_roster_id: str,
) -> bool:
    """Keep assets that still belong to the selected matchup; drop only stale ones."""

    matchup = f"{_text(my_roster_id)}|{_text(partner_roster_id)}"
    previous = _text(state.get(MATCHUP_KEY))
    send = list(state.get(SEND_KEY) or [])
    receive = list(state.get(RECEIVE_KEY) or [])
    next_send = assets_owned_by(send, my_roster_id) if my_roster_id else []
    next_receive = assets_owned_by(receive, partner_roster_id) if partner_roster_id else []
    changed = previous != matchup or next_send != send or next_receive != receive
    state[SEND_KEY] = next_send
    state[RECEIVE_KEY] = next_receive
    state[MATCHUP_KEY] = matchup
    if changed and (next_send != send or next_receive != receive):
        state["trade_analyzer_analyzed_signature"] = ""
        if next_receive != receive:
            state["trade_receive_notice"] = ""
    return changed


def ensure_catalogs(
    state: MutableMapping[str, Any],
    *,
    context_key: str,
    my_roster_id: str,
    partner_roster_id: str,
    players_df,
    my_player_ids: Sequence[str],
    partner_player_ids: Sequence[str],
    my_picks: Sequence[Mapping[str, Any]] | None,
    partner_picks: Sequence[Mapping[str, Any]] | None,
    player_owner_map: Mapping[str, Mapping[str, Any]] | None = None,
    pick_score_multiplier: float = 1.0,
    score_field: str = "value_score",
) -> None:
    cache_key = f"{_text(context_key)}|{_text(my_roster_id)}|{_text(partner_roster_id)}"
    if state.get(CATALOG_CONTEXT_KEY) == cache_key and isinstance(state.get(CATALOG_PLAYERS_ME), list):
        return
    mine = build_side_catalog(
        players_df=players_df,
        player_ids=my_player_ids,
        picks=my_picks,
        player_owner_map=player_owner_map,
        pick_score_multiplier=pick_score_multiplier,
        score_field=score_field,
    )
    partner = build_side_catalog(
        players_df=players_df,
        player_ids=partner_player_ids,
        picks=partner_picks,
        player_owner_map=player_owner_map,
        pick_score_multiplier=pick_score_multiplier,
        score_field=score_field,
    )
    state[CATALOG_CONTEXT_KEY] = cache_key
    state[CATALOG_PLAYERS_ME] = mine["players"]
    state[CATALOG_PICKS_ME] = mine["picks"]
    state[CATALOG_PLAYERS_PARTNER] = partner["players"]
    state[CATALOG_PICKS_PARTNER] = partner["picks"]


def catalog_for_side(state: Mapping[str, Any], *, side: str) -> dict[str, list[dict[str, Any]]]:
    if side == "receive":
        return {
            "players": list(state.get(CATALOG_PLAYERS_PARTNER) or []),
            "picks": list(state.get(CATALOG_PICKS_PARTNER) or []),
        }
    return {
        "players": list(state.get(CATALOG_PLAYERS_ME) or []),
        "picks": list(state.get(CATALOG_PICKS_ME) or []),
    }


def mutate_package(
    state: MutableMapping[str, Any],
    *,
    asset: Mapping[str, Any] | None = None,
    package_key: str,
    action: str,
    index: int = -1,
    partner_roster_id: str = "",
    my_roster_id: str = "",
) -> analyzer_builder.PackageMutation:
    """Add or remove one asset. Invalidates stored analysis; never executes it."""

    send_assets = state.get(SEND_KEY) or []
    receive_assets = state.get(RECEIVE_KEY) or []
    if action == "remove":
        mutation = analyzer_builder.try_remove_asset(
            package_key=package_key,
            index=index,
            send_assets=send_assets,
            receive_assets=receive_assets,
        )
    else:
        mutation = analyzer_builder.try_add_asset(
            asset or {},
            package_key=package_key,
            send_assets=send_assets,
            receive_assets=receive_assets,
            partner_roster_id=partner_roster_id,
            my_roster_id=my_roster_id,
        )
    analyzer_builder.apply_mutation(state, mutation)
    return mutation
