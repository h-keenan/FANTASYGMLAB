"""League standings presentation from canonical Sleeper roster/league fields.

Does not invent wins, points, playoff odds, or seeds. Ranking order is a
presentation sort of Sleeper-stored W-L-T and points-for fields.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    return text if text else default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_nonneg_int(value: object, default: int = 0) -> int:
    parsed = _safe_int(value, default)
    return parsed if parsed >= 0 else default


def sleeper_points_total(settings: Mapping[str, Any] | None, *, against: bool = False) -> float:
    """Combine Sleeper integer + decimal point fields into one total."""

    data = settings if isinstance(settings, Mapping) else {}
    whole_key = "fpts_against" if against else "fpts"
    decimal_key = "fpts_against_decimal" if against else "fpts_decimal"
    whole = _safe_nonneg_int(data.get(whole_key), 0)
    decimal = _safe_nonneg_int(data.get(decimal_key), 0)
    return float(whole) + (float(decimal) / 100.0)


def format_record(wins: int, losses: int, ties: int) -> str:
    label = f"{wins}-{losses}"
    if ties:
        label = f"{label}-{ties}"
    return label


def win_percentage(wins: int, losses: int, ties: int) -> float | None:
    games = wins + losses + ties
    if games <= 0:
        return None
    return (wins + (0.5 * ties)) / games


def format_win_percentage(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def format_points(value: float) -> str:
    try:
        number = float(value)
    except Exception:
        return "0.0"
    return f"{number:,.1f}"


def _division_name_map(league: Mapping[str, Any] | None) -> dict[int, str]:
    league_data = league if isinstance(league, Mapping) else {}
    metadata = (
        league_data.get("metadata")
        if isinstance(league_data.get("metadata"), Mapping)
        else {}
    )
    names: dict[int, str] = {}
    for key, raw in metadata.items():
        text_key = _safe_text(key).lower()
        label = _safe_text(raw)
        if not label:
            continue
        for prefix in ("division_", "divider_"):
            if text_key.startswith(prefix):
                suffix = text_key[len(prefix) :]
                if suffix.isdigit():
                    names[_safe_int(suffix)] = label
    return names


def _playoff_team_count(league_settings: Mapping[str, Any] | None) -> int | None:
    settings = league_settings if isinstance(league_settings, Mapping) else {}
    for key in ("playoff_teams", "playoff_team_count", "num_playoff_teams"):
        value = _safe_int(settings.get(key), 0)
        if value > 0:
            return value
    return None


def playoff_status_label(*, standing_rank: int, playoff_teams: int | None) -> str:
    """Seed / bubble labels from playoff_teams setting only — no odds."""

    if not playoff_teams or standing_rank <= 0:
        return ""
    if standing_rank <= playoff_teams:
        return f"Playoff seed #{standing_rank}"
    if standing_rank == playoff_teams + 1:
        return "On the bubble"
    return "Outside playoff line"


def build_league_standings_bundle(
    *,
    rosters: list[Mapping[str, Any]] | None,
    roster_profiles: Mapping[str, Any] | None = None,
    league: Mapping[str, Any] | None = None,
    team_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Assemble standings rows from already-loaded Sleeper roster/league payloads."""

    league_data = league if isinstance(league, Mapping) else {}
    league_settings = (
        league_data.get("settings")
        if isinstance(league_data.get("settings"), Mapping)
        else {}
    )
    profiles = roster_profiles if isinstance(roster_profiles, Mapping) else {}
    frame_by_roster: dict[str, Mapping[str, Any]] = {}
    if isinstance(team_frame, pd.DataFrame) and not team_frame.empty:
        for _, row in team_frame.iterrows():
            key = _safe_text(row.get("roster_id"))
            if key:
                frame_by_roster[key] = row

    division_names = _division_name_map(league_data)
    rows: list[dict[str, Any]] = []
    for roster in rosters or []:
        if not isinstance(roster, Mapping):
            continue
        roster_id = _safe_text(roster.get("roster_id"))
        if not roster_id:
            continue
        settings = (
            roster.get("settings")
            if isinstance(roster.get("settings"), Mapping)
            else {}
        )
        wins = _safe_nonneg_int(settings.get("wins"), 0)
        losses = _safe_nonneg_int(settings.get("losses"), 0)
        ties = _safe_nonneg_int(settings.get("ties"), 0)
        points_for = sleeper_points_total(settings, against=False)
        points_against = sleeper_points_total(settings, against=True)
        games = wins + losses + ties
        division_id = _safe_int(settings.get("division"), 0)
        profile = profiles.get(roster_id) if isinstance(profiles.get(roster_id), Mapping) else {}
        intel = frame_by_roster.get(roster_id, {})
        team_name = (
            _safe_text(profile.get("team_name"))
            or _safe_text(intel.get("team_name"))
            or "Team"
        )
        owner_name = (
            _safe_text(profile.get("owner_name"))
            or _safe_text(intel.get("owner_name"))
            or "Manager"
        )
        owner_username = (
            _safe_text(profile.get("owner_username"))
            or _safe_text(intel.get("owner_username"))
        )
        avatar_url = (
            _safe_text(profile.get("avatar_url"))
            or _safe_text(intel.get("avatar_url"))
        )
        division_label = ""
        if division_id > 0:
            division_label = division_names.get(division_id) or f"Division {division_id}"
        rows.append(
            {
                "roster_id": roster_id,
                "team_name": team_name,
                "owner_name": owner_name,
                "owner_username": owner_username,
                "avatar_url": avatar_url,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "games": games,
                "record_label": format_record(wins, losses, ties),
                "win_pct": win_percentage(wins, losses, ties),
                "points_for": points_for,
                "points_against": points_against,
                "division_id": division_id if division_id > 0 else None,
                "division_label": division_label,
            }
        )

    standings_df = pd.DataFrame(rows)
    season = _safe_text(league_data.get("season"))
    current_week = _safe_int(
        league_settings.get("leg") or league_settings.get("week"),
        0,
    )
    playoff_teams = _playoff_team_count(league_settings)
    teams_with_games = int((standings_df["games"] > 0).sum()) if not standings_df.empty else 0
    has_divisions = bool(
        not standings_df.empty
        and standings_df["division_id"].notna().any()
        and standings_df["division_id"].fillna(0).gt(0).any()
    )

    if standings_df.empty:
        return {
            "available": False,
            "empty_reason": "unavailable",
            "message": "Standings are unavailable for this league right now.",
            "frame": standings_df,
            "groups": [],
            "season": season,
            "week_label": "",
            "playoff_teams": playoff_teams,
            "has_divisions": False,
            "teams_with_games": 0,
        }

    if teams_with_games <= 0:
        return {
            "available": False,
            "empty_reason": "offseason",
            "message": "Standings will populate once regular-season results are available.",
            "frame": standings_df,
            "groups": [],
            "season": season,
            "week_label": "",
            "playoff_teams": playoff_teams,
            "has_divisions": has_divisions,
            "teams_with_games": 0,
        }

    ordered = standings_df.sort_values(
        by=["wins", "win_pct", "points_for", "points_against", "team_name"],
        ascending=[False, False, False, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    ordered["standing_rank"] = range(1, len(ordered) + 1)
    ordered["win_pct_label"] = ordered["win_pct"].map(format_win_percentage)
    ordered["points_for_label"] = ordered["points_for"].map(format_points)
    ordered["points_against_label"] = ordered["points_against"].map(format_points)
    ordered["playoff_status"] = ordered["standing_rank"].map(
        lambda rank: playoff_status_label(
            standing_rank=int(rank),
            playoff_teams=playoff_teams,
        )
    )
    ordered["on_playoff_line"] = False
    if playoff_teams and playoff_teams < len(ordered):
        ordered.loc[ordered["standing_rank"] == playoff_teams, "on_playoff_line"] = True

    groups: list[dict[str, Any]] = []
    if has_divisions:
        for division_id, group in ordered.groupby("division_id", sort=True):
            if pd.isna(division_id) or int(division_id) <= 0:
                continue
            division_frame = group.sort_values(
                by=["wins", "win_pct", "points_for", "points_against", "team_name"],
                ascending=[False, False, False, True, True],
                kind="mergesort",
            ).reset_index(drop=True)
            division_frame["division_rank"] = range(1, len(division_frame) + 1)
            label = _safe_text(division_frame.iloc[0].get("division_label")) or f"Division {int(division_id)}"
            groups.append(
                {
                    "key": f"division-{int(division_id)}",
                    "label": label,
                    "frame": division_frame,
                    "rank_column": "division_rank",
                }
            )
    if not groups:
        groups = [
            {
                "key": "league",
                "label": "",
                "frame": ordered,
                "rank_column": "standing_rank",
            }
        ]

    week_label = f"Through Week {current_week}" if current_week > 0 else ""
    return {
        "available": True,
        "empty_reason": None,
        "message": "",
        "frame": ordered,
        "groups": groups,
        "season": season,
        "week_label": week_label,
        "playoff_teams": playoff_teams,
        "has_divisions": has_divisions,
        "teams_with_games": teams_with_games,
    }
