from __future__ import annotations

import re
from typing import Any

import pandas as pd


SUPPORTED_DIRECT_PLATFORMS = {"sleeper"}


def normalize_player_id(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if not text:
        return ""
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except (TypeError, ValueError):
        pass
    return text


_NAME_GENERATIONAL_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
# Apostrophes and periods join the letters around them instead of splitting
# a name into extra tokens, so "De'Von" / "DeVon" and "A.J." / "AJ" compare
# equal. Hyphens and spaces still separate tokens.
_NAME_JOINING_PUNCTUATION = re.compile(r"[\'\u2018\u2019\u02bc`.]")


def normalize_player_name(name: Any) -> str:
    if name is None:
        return ""
    text = _NAME_JOINING_PUNCTUATION.sub("", str(name).casefold().strip())
    normalized = re.sub(r"[^a-z0-9]+", " ", text).strip()
    tokens = normalized.split()
    while tokens and tokens[-1] in _NAME_GENERATIONAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def ensure_identity_columns(df_players: pd.DataFrame | None) -> pd.DataFrame:
    if df_players is None:
        return pd.DataFrame()
    df = df_players.copy()
    if df.empty:
        for column in ("player_id", "canonical_player_id", "sleeper_id"):
            if column not in df.columns:
                df[column] = pd.Series(dtype="object")
        return df

    if "player_id" not in df.columns:
        if "canonical_player_id" in df.columns:
            df["player_id"] = df["canonical_player_id"]
        elif "sleeper_id" in df.columns:
            df["player_id"] = df["sleeper_id"]
        else:
            df["player_id"] = ""

    df["player_id"] = df["player_id"].map(normalize_player_id)

    if "canonical_player_id" not in df.columns:
        df["canonical_player_id"] = df["player_id"]
    else:
        df["canonical_player_id"] = df["canonical_player_id"].map(normalize_player_id)
        df["canonical_player_id"] = df["canonical_player_id"].where(
            df["canonical_player_id"].astype(bool),
            df["player_id"],
        )

    if "sleeper_id" not in df.columns:
        df["sleeper_id"] = df["canonical_player_id"]
    else:
        df["sleeper_id"] = df["sleeper_id"].map(normalize_player_id)
        df["sleeper_id"] = df["sleeper_id"].where(
            df["sleeper_id"].astype(bool),
            df["canonical_player_id"],
        )

    # Compatibility contract for the current app: player_id remains canonical.
    df["player_id"] = df["canonical_player_id"].map(normalize_player_id)
    return df


def build_identity_map_from_players(df_players: pd.DataFrame | None) -> dict[str, dict[str, str]]:
    df = ensure_identity_columns(df_players)
    identity_map: dict[str, dict[str, str]] = {}
    if df.empty:
        return identity_map
    for _, row in df.iterrows():
        canonical_id = normalize_player_id(row.get("canonical_player_id") or row.get("player_id"))
        if not canonical_id:
            continue
        identity_map[canonical_id] = {
            "canonical_player_id": canonical_id,
            "player_id": canonical_id,
            "sleeper_id": normalize_player_id(row.get("sleeper_id") or canonical_id),
        }
    return identity_map


def canonicalize_player_id(
    platform: str,
    raw_id: Any,
    identity_map: dict[str, dict[str, str]] | None = None,
) -> str | None:
    platform_key = str(platform or "").strip().casefold()
    normalized_id = normalize_player_id(raw_id)
    if not normalized_id:
        return None
    if platform_key in SUPPORTED_DIRECT_PLATFORMS:
        return normalized_id
    if not identity_map:
        return None
    lookup_key = f"{platform_key}_id"
    for canonical_id, mapping in identity_map.items():
        if normalize_player_id(mapping.get(lookup_key)) == normalized_id:
            return normalize_player_id(mapping.get("canonical_player_id") or canonical_id) or None
    return None


def canonicalize_player_ids(
    platform: str,
    raw_ids: list[Any] | tuple[Any, ...] | set[Any] | None,
    identity_map: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    canonical_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in raw_ids or []:
        canonical_id = canonicalize_player_id(platform, raw_id, identity_map)
        if canonical_id and canonical_id not in seen:
            canonical_ids.append(canonical_id)
            seen.add(canonical_id)
    return canonical_ids


def match_player_by_identity(
    df_players: pd.DataFrame | None,
    name: Any,
    team: Any = None,
    position: Any = None,
    birthdate: Any = None,
) -> str | None:
    df = ensure_identity_columns(df_players)
    if df.empty or "name" not in df.columns:
        return None
    target_name = normalize_player_name(name)
    if not target_name:
        return None

    working = df[df["name"].map(normalize_player_name).eq(target_name)].copy()
    if team is not None and "team" in working.columns:
        team_key = str(team or "").strip().upper()
        if team_key:
            working = working[working["team"].fillna("").astype(str).str.upper().eq(team_key)]
    if position is not None and "position" in working.columns:
        position_key = str(position or "").strip().upper()
        if position_key:
            working = working[working["position"].fillna("").astype(str).str.upper().eq(position_key)]
    if birthdate is not None and "birthdate" in working.columns:
        birthdate_key = str(birthdate or "").strip()
        if birthdate_key:
            working = working[working["birthdate"].fillna("").astype(str).eq(birthdate_key)]

    canonical_ids = sorted(
        {
            normalize_player_id(value)
            for value in working.get("canonical_player_id", pd.Series(dtype="object")).tolist()
            if normalize_player_id(value)
        }
    )
    return canonical_ids[0] if len(canonical_ids) == 1 else None


def resolve_identity_candidates(
    candidates: list[dict[str, Any]],
    *,
    position: Any = None,
    team: Any = None,
) -> tuple[str | None, bool]:
    """Pick one player from same-name candidates.

    Each candidate is ``{"id", "position", "team", "active"}`` (``position``
    may also be a set of eligible positions). Narrows by position, then NFL
    team, then active status, and returns ``(id, False)`` once one id is
    left. Position is a hard filter: a QB is never mapped onto a namesake
    CB. Team and active status only break ties, so a player who changed
    teams still matches. Returns ``(None, True)`` when several ids remain
    after every tiebreaker, and ``(None, False)`` when nothing fits.
    """

    def unique_id(rows: list[dict[str, Any]]) -> str | None:
        ids = {normalize_player_id(row.get("id")) for row in rows}
        ids.discard("")
        return next(iter(ids)) if len(ids) == 1 else None

    working = [row for row in candidates or [] if normalize_player_id(row.get("id"))]
    if not working:
        return None, False
    position_key = str(position or "").strip().upper()
    if position_key:

        def positions_of(row: dict[str, Any]) -> set[str]:
            value = row.get("position")
            values = value if isinstance(value, (set, list, tuple, frozenset)) else [value]
            return {str(item or "").strip().upper() for item in values}

        same_position = [row for row in working if position_key in positions_of(row)]
        if not same_position:
            # Several namesakes, none at this position: reported as ambiguous
            # (never mapped), a single wrong-position namesake as no match.
            return None, unique_id(working) is None
        working = same_position
    found = unique_id(working)
    if found:
        return found, False
    team_key = str(team or "").strip().upper()
    if team_key:
        same_team = [row for row in working if str(row.get("team") or "").strip().upper() == team_key]
        if same_team:
            working = same_team
            found = unique_id(working)
            if found:
                return found, False
    active = [row for row in working if row.get("active") is True and str(row.get("team") or "").strip()]
    if active:
        found = unique_id(active)
        if found:
            return found, False
    return None, True


def resolve_player_row(
    df_players: pd.DataFrame | None,
    platform: str,
    raw_id: Any,
    identity_map: dict[str, dict[str, str]] | None = None,
) -> pd.Series | None:
    df = ensure_identity_columns(df_players)
    canonical_id = canonicalize_player_id(platform, raw_id, identity_map)
    if not canonical_id or df.empty:
        return None
    matches = df[df["canonical_player_id"].map(normalize_player_id).eq(canonical_id)]
    if matches.empty:
        return None
    return matches.iloc[0]
