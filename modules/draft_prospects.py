from typing import Dict, List

import pandas as pd

from modules.roster_needs import classify_roster_rooms


PROSPECTS_2027: Dict[str, List[Dict[str, str]]] = {
    "QB": [
        {
            "name": "Arch Manning",
            "school": "Texas",
            "note": "High-upside passer with early first-round buzz.",
            "source": "CBS/PFF",
        },
        {
            "name": "LaNorris Sellers",
            "school": "South Carolina",
            "note": "Rushing profile gives him fantasy ceiling if the passing develops.",
            "source": "FantasyPros",
        },
        {
            "name": "Julian Sayin",
            "school": "Ohio State",
            "note": "Efficient passer to monitor in superflex formats.",
            "source": "FantasyPros",
        },
    ],
    "RB": [
        {
            "name": "Justice Haynes",
            "school": "Michigan",
            "note": "Potential 2027 RB1 if the health and workload hold.",
            "source": "FantasyPros",
        },
        {
            "name": "Ahmad Hardy",
            "school": "Missouri",
            "note": "Productive runner who could matter if receiving usage grows.",
            "source": "FantasyPros",
        },
        {
            "name": "Kewan Lacy",
            "school": "Ole Miss",
            "note": "Workhorse touchdown profile with early dynasty appeal.",
            "source": "FantasyPros",
        },
    ],
    "WR": [
        {
            "name": "Jeremiah Smith",
            "school": "Ohio State",
            "note": "Elite 2027 dynasty headline prospect.",
            "source": "PFF/CBS/FantasyPros",
        },
        {
            "name": "Cam Coleman",
            "school": "Texas",
            "note": "Big-play X receiver profile with first-round traits.",
            "source": "CBS/FantasyPros",
        },
        {
            "name": "Nick Marsh",
            "school": "Indiana",
            "note": "Athletic outside receiver to track for a breakout season.",
            "source": "FantasyPros",
        },
    ],
    "TE": [
        {
            "name": "Trey'Dez Green",
            "school": "LSU",
            "note": "Huge red-zone target with fantasy-friendly traits.",
            "source": "FantasyPros",
        },
    ],
}


def prospects_for_positions(positions: List[str], limit: int = 6) -> List[Dict[str, str]]:
    seen = set()
    prospects: List[Dict[str, str]] = []
    normalized = [str(pos).upper() for pos in positions if str(pos).upper() in PROSPECTS_2027]
    if not normalized:
        normalized = ["RB", "WR", "QB", "TE"]

    prospect_index = 0
    while len(prospects) < limit:
        added = False
        for pos in normalized:
            position_prospects = PROSPECTS_2027.get(pos, [])
            if prospect_index >= len(position_prospects):
                continue
            prospect = position_prospects[prospect_index]
            key = prospect["name"].casefold()
            if key in seen:
                continue
            seen.add(key)
            item = dict(prospect)
            item["position"] = pos
            prospects.append(item)
            added = True
            if len(prospects) >= limit:
                return prospects
        if not added:
            break
        prospect_index += 1

    return prospects


def draft_watch_positions(
    needed_positions: List[str],
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame | None = None,
    *,
    injury_context: dict | None = None,
    league_settings: dict | None = None,
    team_strategy: str = "",
    limit: int = 4,
) -> List[str]:
    positions = ["QB", "RB", "WR", "TE"]
    needed = [
        str(pos).upper()
        for pos in needed_positions
        if str(pos).upper() in positions
    ]
    roster = roster_df.copy() if roster_df is not None else pd.DataFrame()
    context = injury_context or {}
    settings = league_settings or {}
    room_coverage = classify_roster_rooms(roster, lineup_df, settings)
    needed = [
        position
        for position in needed
        if position not in {"QB", "TE"}
        or room_coverage.get(position, {}).get("true_need")
    ]
    active_injury_positions = {
        str(pos).upper() for pos in context.get("active_injury_positions", []) if pos
    }
    future_injury_positions = {
        str(pos).upper() for pos in context.get("future_injury_positions", []) if pos
    }
    covered_future_positions = {
        str(pos).upper()
        for pos in context.get("covered_future_injury_positions", [])
        if pos
    }
    injury_need_positions = {
        str(pos).upper() for pos in context.get("injury_need_positions", []) if pos
    }

    required = {
        "QB": max(1, int(settings.get("qb_count") or 1)),
        "RB": max(2, int(settings.get("rb_count") or 2)),
        "WR": max(3, int(settings.get("wr_count") or 3)),
        "TE": max(1, int(settings.get("te_count") or 1)),
    }
    if str(settings.get("qb_format") or "") in {"2QB", "Superflex"}:
        required["QB"] = max(2, required["QB"])

    scored: list[tuple[str, float]] = []
    for position in positions:
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
        value_source = (
            position_df["value_score"]
            if not position_df.empty and "value_score" in position_df.columns
            else (
                position_df["dynasty_score"]
                if not position_df.empty and "dynasty_score" in position_df.columns
                else pd.Series(0.0, index=position_df.index)
            )
        )
        values = (
            pd.to_numeric(value_source, errors="coerce").fillna(0)
            if not position_df.empty
            else pd.Series(dtype="float64")
        )
        ages = pd.to_numeric(
            position_df.get("age", pd.Series(float("nan"), index=position_df.index)),
            errors="coerce",
        ) if not position_df.empty else pd.Series(dtype="float64")
        years_exp = pd.to_numeric(
            position_df.get("years_exp", pd.Series(float("nan"), index=position_df.index)),
            errors="coerce",
        ) if not position_df.empty else pd.Series(dtype="float64")
        tiers = (
            position_df.get("player_tier", pd.Series("", index=position_df.index))
            .fillna("")
            .astype(str)
            .str.lower()
            if not position_df.empty
            else pd.Series(dtype="object")
        )
        roles = (
            position_df.get("role", pd.Series("", index=position_df.index))
            .fillna("")
            .astype(str)
            .str.lower()
            if not position_df.empty
            else pd.Series(dtype="object")
        )
        young_limit = 25 if position in {"QB", "TE"} else 24
        young_core = (
            (ages.le(young_limit) | years_exp.le(2))
            & (
                values.ge(40)
                | tiers.isin({"elite", "star", "core starter"})
                | roles.eq("core")
            )
        )
        score = 0.0
        if position in needed:
            score += 70.0 - (needed.index(position) * 8.0)
        room = room_coverage.get(position, {})
        if room.get("short_term_need"):
            score += 75.0
        if room.get("long_term_need"):
            score += 34.0
        elif position in future_injury_positions:
            score -= 28.0
        if position in injury_need_positions:
            score += 45.0
        elif position in active_injury_positions:
            score += 20.0
        if (
            position in future_injury_positions
            and position in covered_future_positions
        ):
            score -= 55.0
        if position in {"QB", "TE"} and not room.get("true_need"):
            score -= 75.0
        if not ages.empty and ages.notna().any():
            average_age = float(ages.mean())
            age_threshold = 30.0 if position == "QB" else 28.5 if position == "TE" else 27.0
            if average_age >= age_threshold:
                score += 20.0
        if team_strategy in {"rebuild", "tank"} and bool(young_core.any()):
            score -= 8.0
        scored.append((position, score))

    eligible_positions = {
        position
        for position in positions
        if position not in {"QB", "TE"}
        or room_coverage.get(position, {}).get("true_need")
    }
    ordered = [
        position
        for position, _ in sorted(
            scored,
            key=lambda item: (-item[1], positions.index(item[0])),
        )
        if position in eligible_positions
    ]
    return ordered[: max(1, min(limit, len(positions)))]
