from typing import Any

import pandas as pd


CORE_POSITIONS = ("QB", "RB", "WR", "TE")
STRONG_TIERS = {"elite", "star", "core starter", "starter"}
PLAYABLE_OPPORTUNITIES = {
    "elite opportunity",
    "strong opportunity",
    "starter at risk",
    "committee back",
    "backup with upside",
}
DEVELOPMENTAL_LABELS = {
    "developmental",
    "rookie",
    "prospect",
    "stash",
    "backup with upside",
}
UNAVAILABLE_STATUS_TERMS = {
    "ir",
    "out",
    "inactive",
    "pup",
    "nfi",
    "suspended",
    "injured reserve",
}


def _number(value, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if pd.notna(number) else default


def _text(row, *fields: str) -> str:
    return " ".join(
        str(row.get(field) or "").strip().lower()
        for field in fields
    )


def _is_unavailable(row) -> bool:
    status = _text(row, "status", "injury_status")
    tokens = set(status.replace("/", " ").replace("-", " ").split())
    return bool(
        tokens.intersection({"ir", "pup", "nfi"})
        or any(
            term in status
            for term in {
                "out",
                "inactive",
                "suspended",
                "injured reserve",
            }
        )
    )


def _is_developmental(row, position: str) -> bool:
    age = _number(row.get("age"), 99.0)
    years_exp = _number(row.get("years_exp"), 99.0)
    role_text = _text(
        row,
        "role",
        "role_label",
        "player_tier",
        "tier_label",
        "opportunity_label",
    )
    age_limit = 25.0 if position == "QB" else 24.0
    return (
        age <= age_limit
        and years_exp <= 2.0
        and any(label in role_text for label in DEVELOPMENTAL_LABELS)
    )


def _is_core_young_asset(row, position: str) -> bool:
    age = _number(row.get("age"), 99.0)
    age_limit = 27.0 if position == "QB" else 25.0 if position == "TE" else 24.0
    role_text = _text(row, "role", "role_label", "player_tier", "tier_label")
    value = max(
        _number(row.get("value_score")),
        _number(row.get("dynasty_score")),
        _number(row.get("market_score")),
    )
    return age <= age_limit and (
        any(label in role_text for label in ("core", "elite", "star", "untouchable"))
        or value >= 55.0
    )


def _is_weekly_starter(row, lineup_starter_ids: set[str]) -> bool:
    player_id = str(row.get("player_id") or "").strip()
    if player_id and player_id in lineup_starter_ids:
        return True
    depth_slot = _number(
        row.get("depth_chart_slot", row.get("depth_chart_order")),
        99.0,
    )
    role_text = _text(row, "role", "role_label", "player_tier", "tier_label")
    opportunity = str(row.get("opportunity_label") or "").strip().lower()
    return bool(
        row.get("projected_starter")
        or depth_slot == 1.0
        or "starter" in role_text
        or opportunity in {
            "elite opportunity",
            "strong opportunity",
            "starter at risk",
        }
    )


def _is_playable_cover(row, position: str) -> bool:
    if _is_unavailable(row):
        return False
    tier = str(
        row.get("player_tier")
        or row.get("tier_label")
        or ""
    ).strip().lower()
    opportunity = str(row.get("opportunity_label") or "").strip().lower()
    value = max(
        _number(row.get("value_score")),
        _number(row.get("dynasty_score")),
        _number(row.get("market_score")),
    )
    threshold = 24.0 if position == "QB" else 20.0 if position == "TE" else 18.0
    return (
        tier in STRONG_TIERS
        or opportunity in PLAYABLE_OPPORTUNITIES
        or value >= threshold
    )


def classify_roster_rooms(
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame | None = None,
    league_settings: dict | None = None,
) -> dict[str, dict[str, Any]]:
    roster = roster_df.copy() if roster_df is not None else pd.DataFrame()
    settings = league_settings or {}
    lineup = lineup_df if lineup_df is not None else pd.DataFrame()
    starter_ids = {
        str(player_id)
        for player_id in lineup.loc[
            lineup.get(
                "suggested_starter",
                pd.Series(False, index=lineup.index),
            ).fillna(False),
            "player_id",
        ].tolist()
        if player_id is not None
    } if not lineup.empty and "player_id" in lineup.columns else set()

    superflex = (
        int(settings.get("superflex_count") or 0) > 0
        or int(settings.get("qb_count") or 1) >= 2
        or str(settings.get("qb_format") or "").strip().lower()
        in {"2qb", "superflex"}
    )
    required = {
        "QB": 2 if superflex else 1,
        "RB": max(1, int(settings.get("rb_count") or 2)),
        "WR": max(1, int(settings.get("wr_count") or 3)),
        "TE": max(1, int(settings.get("te_count") or 1)),
    }
    if bool(settings.get("te_premium")):
        required["TE"] = max(required["TE"], 1)

    rooms: dict[str, dict[str, Any]] = {}
    for position in CORE_POSITIONS:
        position_df = (
            roster[
                roster.get("position", pd.Series("", index=roster.index))
                .fillna("")
                .astype(str)
                .str.upper()
                .eq(position)
            ].copy()
            if not roster.empty
            else pd.DataFrame()
        )
        active_starters = []
        playable_cover = []
        developmental = []
        developmental_depth = []
        core_young = []
        injured_active = []
        injured_future = []

        for _, row in position_df.iterrows():
            player_id = str(row.get("player_id") or "").strip()
            weekly_starter = _is_weekly_starter(row, starter_ids)
            core_asset = _is_core_young_asset(row, position)
            future_asset = _is_developmental(row, position) or core_asset
            unavailable = _is_unavailable(row)
            playable = _is_playable_cover(row, position)

            if core_asset:
                core_young.append(player_id)
            if future_asset:
                developmental.append(player_id)
                if not weekly_starter or unavailable:
                    developmental_depth.append(player_id)
            if unavailable:
                if weekly_starter and not future_asset:
                    injured_active.append(player_id)
                elif future_asset:
                    injured_future.append(player_id)
                continue
            if weekly_starter and playable:
                active_starters.append(player_id)
            elif playable:
                playable_cover.append(player_id)

        active_count = len(active_starters)
        playable_count = len(playable_cover)
        future_count = len(set(developmental))
        future_depth_count = len(set(developmental_depth))
        core_count = len(set(core_young))
        weekly_coverage = active_count + playable_count

        short_term_need = weekly_coverage < required[position]
        long_term_need = core_count == 0 and future_count == 0
        true_need = short_term_need or long_term_need
        need_type = ""
        if short_term_need:
            need_type = "short-term starter coverage"
        elif long_term_need:
            need_type = "long-term upside"
        elif injured_future:
            need_type = "active room covered; future asset injured"
        elif playable_count:
            need_type = "developmental depth already present"

        if position == "QB" and not superflex:
            if active_count >= 1 and (
                playable_count >= 1 or future_depth_count >= 1
            ):
                true_need = False
                short_term_need = False
                long_term_need = False
                need_type = "starter covered with backup/future depth"
            elif active_count >= 1:
                true_need = True
                short_term_need = True
                need_type = "short-term backup only"
        if position == "TE":
            if core_count >= 1 and weekly_coverage >= required[position]:
                true_need = False
                short_term_need = False
                long_term_need = False
                need_type = (
                    "active room covered; future asset injured"
                    if injured_future
                    else "core asset with playable active cover"
                )
            elif bool(settings.get("te_premium")) and weekly_coverage < required[position] + 1:
                true_need = True
                need_type = "TE-premium depth"

        rooms[position] = {
            "position": position,
            "required_starters": required[position],
            "superflex": superflex if position == "QB" else False,
            "active_starters": active_starters,
            "playable_backups": playable_cover,
            "developmental_assets": list(dict.fromkeys(developmental)),
            "developmental_depth_assets": list(
                dict.fromkeys(developmental_depth)
            ),
            "core_young_assets": list(dict.fromkeys(core_young)),
            "injured_active_contributors": injured_active,
            "injured_future_assets": injured_future,
            "active_coverage_count": weekly_coverage,
            "future_coverage_count": future_count,
            "short_term_need": short_term_need,
            "long_term_need": long_term_need,
            "true_need": true_need,
            "need_type": need_type,
        }
    return rooms


def true_roster_needs(
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame | None,
    league_settings: dict | None,
    baseline_needs: list[str] | None = None,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    rooms = classify_roster_rooms(roster_df, lineup_df, league_settings)
    needs: list[str] = []
    for position in baseline_needs or []:
        position = str(position).upper()
        if position not in CORE_POSITIONS or position in needs:
            continue
        if position in {"QB", "TE"} and not rooms[position]["true_need"]:
            continue
        needs.append(position)
    for position in CORE_POSITIONS:
        if rooms[position]["true_need"] and position not in needs:
            needs.append(position)
    return needs, rooms
