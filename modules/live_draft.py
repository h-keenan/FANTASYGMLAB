"""Read-only Sleeper live draft helpers."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd
import requests

from modules import performance
from modules.sleeper import SLEEPER_BASE


LIVE_DRAFT_POLL_INTERVAL_SECONDS = 12
LIVE_DRAFT_READ_ONLY_LABEL = "Read-only live draft assistant"
LIVE_DRAFT_SUPPORTED_STATUSES = {"drafting", "paused", "pre_draft", "complete"}
LIVE_DRAFT_WRITE_METHOD_TOKENS: tuple[str, ...] = ()


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def normalize_draft_status(status: Any) -> str:
    text = safe_text(status, "unknown").casefold().replace("-", "_").replace(" ", "_")
    if text in {"drafting", "in_progress", "inprogress", "started", "active"}:
        return "drafting"
    if text in {"paused", "pause"}:
        return "paused"
    if text in {"pre_draft", "predraft", "scheduled", "setup", "not_started"}:
        return "pre_draft"
    if text in {"complete", "completed", "done"}:
        return "complete"
    return text or "unknown"


def draft_round_count(draft: dict[str, Any] | None) -> int:
    draft = draft if isinstance(draft, dict) else {}
    settings = draft.get("settings") if isinstance(draft.get("settings"), dict) else {}
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    for key in ("rounds", "draft_rounds", "num_rounds"):
        value = safe_int(settings.get(key) or metadata.get(key) or draft.get(key), 0)
        if value:
            return value
    return 0


def draft_team_count(draft: dict[str, Any] | None, rosters: list[dict[str, Any]] | None = None) -> int:
    draft = draft if isinstance(draft, dict) else {}
    settings = draft.get("settings") if isinstance(draft.get("settings"), dict) else {}
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    for key in ("teams", "num_teams", "slots"):
        value = safe_int(settings.get(key) or metadata.get(key) or draft.get(key), 0)
        if value:
            return value
    return len(rosters or [])


def discover_live_drafts(
    league_id: str,
    *,
    fetch_league_drafts: Callable[[str], list[dict[str, Any]]],
    fetch_draft: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    if not league_id:
        return {"drafts": [], "active_draft": None, "error": "league_missing"}
    try:
        draft_stubs = fetch_league_drafts(league_id) or []
    except Exception:
        return {"drafts": [], "active_draft": None, "error": "draft_discovery_failed"}

    drafts: list[dict[str, Any]] = []
    for stub in draft_stubs:
        draft_id = safe_text((stub or {}).get("draft_id") or (stub or {}).get("id"))
        detail: dict[str, Any] = {}
        if draft_id:
            try:
                detail = fetch_draft(draft_id) or {}
            except Exception:
                detail = {}
        merged = dict(stub or {})
        merged.update(detail)
        merged["draft_id"] = draft_id or safe_text(merged.get("draft_id") or merged.get("id"))
        merged["status"] = normalize_draft_status(merged.get("status"))
        merged["rounds"] = draft_round_count(merged)
        drafts.append(merged)

    priority = {"drafting": 0, "paused": 1, "pre_draft": 2, "complete": 3}
    drafts.sort(
        key=lambda draft: (
            priority.get(normalize_draft_status(draft.get("status")), 9),
            -safe_int(draft.get("season"), 0),
            safe_text(draft.get("draft_id")),
        )
    )
    active = next(
        (draft for draft in drafts if normalize_draft_status(draft.get("status")) in LIVE_DRAFT_SUPPORTED_STATUSES),
        drafts[0] if drafts else None,
    )
    return {"drafts": drafts, "active_draft": active, "error": ""}


def fetch_sleeper_draft_picks(draft_id: str) -> tuple[list[dict[str, Any]], str]:
    """Fetch draft picks from Sleeper without using a cached helper."""
    if not draft_id:
        return [], "draft_missing"
    try:
        with performance.time_block("live_draft_poll_picks", category="sleeper"):
            response = requests.get(f"{SLEEPER_BASE}/draft/{draft_id}/picks", timeout=8)
        if response.status_code != 200:
            return [], f"sleeper_status_{response.status_code}"
        data = response.json()
        return (data if isinstance(data, list) else []), ""
    except Exception:
        return [], "sleeper_unavailable"


def pick_player_id(pick: dict[str, Any] | None) -> str:
    pick = pick if isinstance(pick, dict) else {}
    metadata = pick.get("metadata") if isinstance(pick.get("metadata"), dict) else {}
    return safe_text(
        pick.get("player_id")
        or pick.get("drafted_player_id")
        or metadata.get("player_id")
        or metadata.get("drafted_player_id")
    )


def pick_roster_id(pick: dict[str, Any] | None) -> int:
    pick = pick if isinstance(pick, dict) else {}
    metadata = pick.get("metadata") if isinstance(pick.get("metadata"), dict) else {}
    return safe_int(pick.get("roster_id") or metadata.get("roster_id"), 0)


def pick_number(pick: dict[str, Any] | None) -> int:
    pick = pick if isinstance(pick, dict) else {}
    return safe_int(pick.get("pick_no") or pick.get("pick") or pick.get("draft_slot"), 0)


def build_draft_order_maps(
    draft: dict[str, Any] | None,
    rosters: list[dict[str, Any]] | None,
) -> dict[str, dict[Any, Any]]:
    draft = draft if isinstance(draft, dict) else {}
    rosters = rosters or []
    owner_to_roster = {
        safe_text(roster.get("owner_id")): safe_int(roster.get("roster_id"), 0)
        for roster in rosters
        if safe_text(roster.get("owner_id")) and safe_int(roster.get("roster_id"), 0)
    }
    roster_to_owner = {roster_id: owner_id for owner_id, roster_id in owner_to_roster.items()}
    draft_order = draft.get("draft_order") if isinstance(draft.get("draft_order"), dict) else {}
    slot_to_roster: dict[int, int] = {}
    roster_to_slot: dict[int, int] = {}
    slot_to_owner: dict[int, str] = {}

    for raw_owner_or_roster, raw_slot in draft_order.items():
        slot = safe_int(raw_slot, 0)
        if not slot:
            continue
        owner_or_roster = safe_text(raw_owner_or_roster)
        roster_id = safe_int(owner_or_roster, 0)
        if owner_or_roster in owner_to_roster:
            roster_id = owner_to_roster[owner_or_roster]
            slot_to_owner[slot] = owner_or_roster
        if roster_id:
            slot_to_roster[slot] = roster_id
            roster_to_slot[roster_id] = slot

    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    slot_map = metadata.get("slot_to_roster_id") if isinstance(metadata.get("slot_to_roster_id"), dict) else {}
    for raw_slot, raw_roster in slot_map.items():
        slot = safe_int(raw_slot, 0)
        roster_id = safe_int(raw_roster, 0)
        if slot and roster_id:
            slot_to_roster[slot] = roster_id
            roster_to_slot[roster_id] = slot
            owner_id = roster_to_owner.get(roster_id)
            if owner_id:
                slot_to_owner[slot] = owner_id

    return {
        "slot_to_roster": slot_to_roster,
        "roster_to_slot": roster_to_slot,
        "slot_to_owner": slot_to_owner,
        "owner_to_roster": owner_to_roster,
    }


def draft_slot_for_pick(pick_no: int, team_count: int, *, snake: bool = True) -> int:
    if pick_no <= 0 or team_count <= 0:
        return 0
    round_no = (pick_no - 1) // team_count + 1
    pick_in_round = (pick_no - 1) % team_count + 1
    if snake and round_no % 2 == 0:
        return team_count - pick_in_round + 1
    return pick_in_round


def current_pick_number(picks: list[dict[str, Any]] | None) -> int:
    used = [pick_number(pick) for pick in picks or [] if pick_number(pick) > 0]
    return (max(used) + 1) if used else len(picks or []) + 1


def picks_until_next_selection(
    *,
    current_pick: int,
    my_slot: int,
    team_count: int,
    rounds: int,
    snake: bool = True,
) -> int | None:
    if current_pick <= 0 or my_slot <= 0 or team_count <= 0:
        return None
    total = max(rounds, 0) * team_count if rounds else current_pick + team_count * 4
    for pick_no in range(current_pick, total + 1):
        if draft_slot_for_pick(pick_no, team_count, snake=snake) == my_slot:
            return max(0, pick_no - current_pick)
    return None


def enrich_pick_rows(
    picks: list[dict[str, Any]] | None,
    *,
    df_players: pd.DataFrame,
    roster_profiles: dict[str, dict[str, Any]] | None,
    my_roster_id: Any = None,
) -> list[dict[str, Any]]:
    roster_profiles = roster_profiles or {}
    player_lookup = {}
    if df_players is not None and not df_players.empty and "player_id" in df_players.columns:
        player_lookup = {
            safe_text(row.get("player_id")): row
            for row in df_players.fillna("").to_dict("records")
            if safe_text(row.get("player_id"))
        }
    rows: list[dict[str, Any]] = []
    for idx, pick in enumerate(picks or [], start=1):
        player_id = pick_player_id(pick)
        player = player_lookup.get(player_id, {})
        roster_id = pick_roster_id(pick)
        profile = roster_profiles.get(str(roster_id), {})
        round_no = safe_int(pick.get("round"), 0)
        draft_slot = safe_int(pick.get("draft_slot"), 0)
        pick_no = pick_number(pick) or idx
        rows.append(
            {
                "pick_no": pick_no,
                "round": round_no,
                "draft_slot": draft_slot,
                "round_pick": f"{round_no}.{draft_slot:02d}" if round_no and draft_slot else f"Pick {pick_no}",
                "player_id": player_id,
                "player_name": safe_text(
                    pick.get("metadata", {}).get("first_name") + " " + pick.get("metadata", {}).get("last_name")
                    if isinstance(pick.get("metadata"), dict)
                    and pick.get("metadata", {}).get("first_name")
                    and pick.get("metadata", {}).get("last_name")
                    else player.get("name"),
                    "Unknown Player",
                ),
                "position": safe_text(player.get("position") or (pick.get("metadata") or {}).get("position"), "UNK"),
                "team": safe_text(player.get("team") or (pick.get("metadata") or {}).get("team"), ""),
                "roster_id": roster_id,
                "fantasy_team": safe_text(profile.get("team_name") or profile.get("owner_name"), f"Roster {roster_id}" if roster_id else "Unknown Team"),
                "timestamp": pick.get("picked_at") or pick.get("created") or "",
                "is_mine": bool(my_roster_id is not None and str(roster_id) == str(my_roster_id)),
                "raw": pick,
            }
        )
    return sorted(rows, key=lambda row: safe_int(row.get("pick_no"), 0))


def drafted_player_ids(picks: list[dict[str, Any]] | None) -> set[str]:
    return {player_id for player_id in (pick_player_id(pick) for pick in picks or []) if player_id}


def available_player_pool(
    df_players: pd.DataFrame,
    picks: list[dict[str, Any]] | None,
    *,
    score_field: str,
) -> pd.DataFrame:
    if df_players is None or df_players.empty:
        return pd.DataFrame()
    pool = df_players.copy()
    drafted = drafted_player_ids(picks)
    if "player_id" in pool.columns:
        pool = pool[~pool["player_id"].astype(str).isin(drafted)].copy()
    if score_field not in pool.columns and "value_score" in pool.columns:
        score_field = "value_score"
    if score_field in pool.columns:
        pool[score_field] = pd.to_numeric(pool[score_field], errors="coerce").fillna(0)
        pool = pool.sort_values(score_field, ascending=False)
    return pool.reset_index(drop=True)


def roster_position_needs(roster_df: pd.DataFrame, league_settings: dict[str, Any] | None = None) -> list[str]:
    if roster_df is None or roster_df.empty or "position" not in roster_df.columns:
        return ["RB", "WR", "TE", "QB"]
    counts = Counter(safe_text(pos).upper() for pos in roster_df["position"].tolist())
    settings = league_settings or {}
    qb_slots = safe_int(settings.get("qb_slots"), 1) + safe_int(settings.get("superflex_slots"), 0)
    target = {
        "QB": 3 if qb_slots >= 2 else 2,
        "RB": 5,
        "WR": 6,
        "TE": 2,
    }
    needs = sorted(target, key=lambda pos: (counts.get(pos, 0) - target[pos], counts.get(pos, 0), pos))
    return needs


def build_live_draft_recommendations(
    available_pool: pd.DataFrame,
    *,
    roster_df: pd.DataFrame,
    league_settings: dict[str, Any],
    score_field: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if available_pool is None or available_pool.empty:
        return []
    pool = available_pool.copy()
    if score_field not in pool.columns and "value_score" in pool.columns:
        score_field = "value_score"
    if score_field in pool.columns:
        pool[score_field] = pd.to_numeric(pool[score_field], errors="coerce").fillna(0)
    else:
        pool[score_field] = 0
    needs = roster_position_needs(roster_df, league_settings)
    recs: list[dict[str, Any]] = []

    def row_to_rec(label: str, row: pd.Series, reason: str) -> dict[str, Any]:
        return {
            "label": label,
            "player_id": safe_text(row.get("player_id")),
            "name": safe_text(row.get("name"), "Player"),
            "position": safe_text(row.get("position"), ""),
            "team": safe_text(row.get("team"), ""),
            "value": float(row.get(score_field) or 0),
            "tier": safe_text(row.get("player_tier") or row.get("tier"), "Board Value"),
            "reason": reason,
        }

    top = pool.iloc[0]
    recs.append(row_to_rec("Best Available", top, "Highest remaining player by the current league-aware value field."))
    need_pool = pool[pool.get("position", pd.Series(dtype=str)).astype(str).str.upper().isin(needs[:2])]
    if not need_pool.empty:
        need = need_pool.iloc[0]
        recs.append(row_to_rec("Best Fit", need, f"Addresses {safe_text(need.get('position')).upper()} while staying near the top of the board."))
    safe_pool = pool[pool.get("age", pd.Series(dtype=float)).apply(lambda age: safe_int(age, 99) <= 27)]
    if not safe_pool.empty:
        recs.append(row_to_rec("Safe Pick", safe_pool.iloc[0], "Young enough to preserve dynasty value without forcing a reach."))
    upside_pool = pool[pool.get("age", pd.Series(dtype=float)).apply(lambda age: safe_int(age, 99) <= 24)]
    if not upside_pool.empty:
        recs.append(row_to_rec("Upside Pick", upside_pool.iloc[0], "Younger profile with room to gain market value if role expands."))
    position_need = needs[0] if needs else safe_text(top.get("position"))
    position_pool = pool[pool.get("position", pd.Series(dtype=str)).astype(str).str.upper() == position_need]
    if not position_pool.empty:
        recs.append(row_to_rec("Position Need", position_pool.iloc[0], f"{position_need} is the thinnest current roster room by simple construction check."))

    deduped: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for rec in recs:
        pair = (rec["label"], rec["player_id"])
        if rec["label"] in seen_labels and pair in seen_pairs:
            continue
        seen_labels.add(rec["label"])
        seen_pairs.add(pair)
        deduped.append(rec)
    return deduped[:limit]



LIVE_DRAFT_TIERS = ("Elite", "Star", "Core Starter", "Starter", "Upside", "Depth")


def _setting_truthy(settings: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = settings.get(key)
        if isinstance(value, bool):
            return value
        if safe_text(value).casefold() in {"1", "true", "yes", "on", "superflex", "2qb", "te premium", "tep"}:
            return True
        if safe_int(value, 0) > 0:
            return True
    return False


def _is_rookie(row: pd.Series) -> bool:
    if _setting_truthy(row.to_dict(), "rookie", "is_rookie"):
        return True
    experience = row.get("years_exp", row.get("experience"))
    return experience is not None and safe_int(experience, 99) == 0


def _draft_kind(draft: dict[str, Any] | None) -> str:
    draft = draft if isinstance(draft, dict) else {}
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    text = " ".join(
        safe_text(value).casefold()
        for value in (metadata.get("type"), metadata.get("name"), draft.get("type"))
        if safe_text(value)
    )
    return "rookie" if "rookie" in text else "startup"


def _strategy_name(league_settings: dict[str, Any]) -> str:
    return safe_text(
        league_settings.get("team_strategy")
        or league_settings.get("strategy")
        or league_settings.get("team_direction"),
        "balanced",
    ).casefold()


def _age_strategy_adjustment(
    *, age: int, position: str, dynasty: bool, rookie_draft: bool, strategy: str
) -> float:
    """A deliberately modest dynasty tie-breaker, capped well below one value tier."""
    if not dynasty or rookie_draft or age <= 0:
        return 0.0
    peak_age = 27 if position == "QB" else 25 if position == "RB" else 26
    delta = age - peak_age
    if delta <= 0:
        youth = min(1.5, abs(delta) * 0.35)
        return youth * (1.0 if strategy in {"rebuild", "rebuilder", "tank"} else 0.45)
    penalty_rate = 0.65
    if strategy in {"contender", "compete", "win now", "win_now"}:
        penalty_rate = 0.25
    elif strategy in {"rebuild", "rebuilder", "tank"}:
        penalty_rate = 0.8
    return -min(3.0, delta * penalty_rate)


def _tier_for_rank(rank: int, total: int, existing: str = "") -> str:
    normalized = safe_text(existing).casefold()
    aliases = {
        "elite": "Elite", "star": "Star", "core starter": "Core Starter",
        "starter": "Starter", "upside": "Upside", "depth": "Depth",
        "contributor": "Starter", "developmental": "Upside",
    }
    if normalized in aliases:
        return aliases[normalized]
    pct = rank / max(total, 1)
    if pct <= 0.03:
        return "Elite"
    if pct <= 0.10:
        return "Star"
    if pct <= 0.25:
        return "Core Starter"
    if pct <= 0.50:
        return "Starter"
    if pct <= 0.78:
        return "Upside"
    return "Depth"



def resolve_draft_board_score_field(
    players: pd.DataFrame,
    requested_field: str,
    league_settings: dict[str, Any] | None = None,
) -> str:
    """Use a neutral league value for draft boards, never a strategy-specific rebuild lens."""
    columns = set(players.columns) if players is not None else set()
    league_format = safe_text((league_settings or {}).get("league_format"), "Dynasty").casefold()
    if "dynasty" not in league_format and "keeper" not in league_format and "value_score" in columns:
        return "value_score"
    if "dynasty_score" in columns:
        return "dynasty_score"
    if requested_field in columns and requested_field != "rebuild_score":
        return requested_field
    if "value_score" in columns:
        return "value_score"
    return requested_field


def build_live_draft_rankings(
    available_pool: pd.DataFrame,
    *,
    roster_df: pd.DataFrame,
    league_settings: dict[str, Any],
    score_field: str,
    draft: dict[str, Any] | None = None,
    picks_until_mine: int | None = None,
    previous_ranks: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Rank the available pool without replacing the app's base valuation model."""
    if available_pool is None or available_pool.empty:
        return pd.DataFrame()
    board = available_pool.loc[:, ~available_pool.columns.duplicated(keep="last")].copy()
    score_field = resolve_draft_board_score_field(board, score_field, league_settings)
    board["base_value"] = pd.to_numeric(board.get(score_field, 0), errors="coerce").fillna(0.0)
    settings = league_settings or {}
    league_format = safe_text(settings.get("league_format"), "Dynasty").casefold()
    dynasty = "dynasty" in league_format or "keeper" in league_format
    qb_format = safe_text(settings.get("qb_format"), "1QB").casefold()
    superflex = "super" in qb_format or "2qb" in qb_format or safe_int(settings.get("superflex_slots"), 0) > 0
    te_premium = _setting_truthy(settings, "te_premium", "tep") or float(settings.get("te_reception_bonus") or 0) > 0
    rookie_draft = _draft_kind(draft) == "rookie"
    strategy = _strategy_name(settings)
    needs = roster_position_needs(roster_df, settings)
    need_rank = {position: max(0, 4 - index) for index, position in enumerate(needs)}
    counts = Counter(
        safe_text(value).upper()
        for value in (roster_df.get("position", pd.Series(dtype=str)).tolist() if roster_df is not None else [])
    )
    starters = {
        "QB": max(1, safe_int(settings.get("qb_slots"), 1) + safe_int(settings.get("superflex_slots"), 0)),
        "RB": max(2, safe_int(settings.get("rb_slots"), 2)),
        "WR": max(2, safe_int(settings.get("wr_slots"), 2)),
        "TE": max(1, safe_int(settings.get("te_slots"), 1)),
    }
    pool_position_counts = Counter(
        board.get("position", pd.Series(dtype=str)).astype(str).str.upper().tolist()
    )
    components: list[dict[str, Any]] = []
    for _, row in board.iterrows():
        position = safe_text(row.get("position"), "UNK").upper()
        age = safe_int(row.get("age"), 0)
        rookie = _is_rookie(row)
        format_adjustment = 0.0
        if position == "QB" and superflex:
            format_adjustment += 7.0
        if position == "TE" and te_premium:
            format_adjustment += 4.0
        if rookie_draft and not rookie:
            format_adjustment -= 1000.0
        scarcity = min(4.0, max(0.0, (starters.get(position, 1) * 2 - counts.get(position, 0)) * 1.25))
        roster_fit = min(5.0, float(need_rank.get(position, 0)) + scarcity * 0.35)
        age_adjustment = _age_strategy_adjustment(
            age=age, position=position, dynasty=dynasty, rookie_draft=rookie_draft, strategy=strategy
        )
        availability = 0.0
        if picks_until_mine is not None and picks_until_mine > 0:
            pool_position_count = pool_position_counts.get(position, 0)
            availability = min(2.0, max(0.0, (picks_until_mine - pool_position_count) * 0.25))
        components.append(
            {
                "format_adjustment": format_adjustment,
                "scarcity_score": scarcity,
                "roster_fit_score": roster_fit,
                "age_strategy_adjustment": age_adjustment,
                "availability_adjustment": availability,
            }
        )
    component_df = pd.DataFrame(components, index=board.index)
    for component_name in component_df.columns:
        board[component_name] = component_df[component_name]
    board["league_adjusted_draft_score"] = (
        board["base_value"]
        + board["format_adjustment"]
        + board["scarcity_score"]
        + board["roster_fit_score"]
        + board["age_strategy_adjustment"]
        + board["availability_adjustment"]
    )
    board = board.sort_values(
        ["league_adjusted_draft_score", "base_value", "age"],
        ascending=[False, False, True],
        kind="stable",
    ).reset_index(drop=True)
    board["overall_rank"] = range(1, len(board) + 1)
    board["position_rank"] = board.groupby(board.get("position", pd.Series(dtype=str)).astype(str).str.upper()).cumcount() + 1
    board["is_rookie"] = board.apply(_is_rookie, axis=1)
    board["tier"] = [
        _tier_for_rank(rank, len(board), safe_text(row.get("player_tier") or row.get("tier")))
        for rank, (_, row) in enumerate(board.iterrows(), start=1)
    ]
    previous_ranks = previous_ranks or {}
    board["movement"] = [
        (previous_ranks.get(safe_text(row.get("player_id"))) - safe_int(row.get("overall_rank"), 0))
        if safe_text(row.get("player_id")) in previous_ranks else 0
        for _, row in board.iterrows()
    ]
    board["recommendation_label"] = ""
    board["recommendation_reason"] = "Strongest blend of existing value, format, scarcity, and roster construction."
    if len(board):
        board.loc[0, ["recommendation_label", "recommendation_reason"]] = [
            "Best Available", "Highest remaining league-adjusted score while preserving the base board."
        ]
    fit_idx = board["roster_fit_score"].idxmax()
    if fit_idx != 0:
        board.loc[fit_idx, ["recommendation_label", "recommendation_reason"]] = [
            "Best Fit", f"Best available match for the current {safe_text(board.loc[fit_idx, 'position'])} roster need."
        ]
    unlabelled = board.index[board["recommendation_label"] == ""].tolist()
    if unlabelled:
        safe_idx = max(unlabelled, key=lambda idx: (board.loc[idx, "base_value"], -abs(board.loc[idx, "age_strategy_adjustment"])))
        board.loc[safe_idx, ["recommendation_label", "recommendation_reason"]] = [
            "Safe Pick", "High baseline value with limited strategy or age downside."
        ]
    unlabelled = board.index[board["recommendation_label"] == ""].tolist()
    if unlabelled:
        upside_idx = min(unlabelled, key=lambda idx: (safe_int(board.loc[idx, "age"], 99), -board.loc[idx, "base_value"]))
        board.loc[upside_idx, ["recommendation_label", "recommendation_reason"]] = [
            "Upside Pick", "Youth and role runway add upside without overriding the base tier."
        ]
    unlabelled = board.index[board["recommendation_label"] == ""].tolist()
    if unlabelled and needs:
        need_candidates = [idx for idx in unlabelled if safe_text(board.loc[idx, "position"]).upper() == needs[0]]
        if need_candidates:
            idx = need_candidates[0]
            board.loc[idx, ["recommendation_label", "recommendation_reason"]] = [
                "Position Need", f"{needs[0]} is the thinnest current roster room."
            ]
    if len(board) >= 8:
        reach_idx = board.index[-1]
        board.loc[reach_idx, ["recommendation_label", "recommendation_reason"]] = [
            "Avoid / Reach", "Current price and fit trail the stronger options still available."
        ]
    return board



def build_live_team_rankings(
    picks: list[dict[str, Any]] | None,
    *,
    df_players: pd.DataFrame,
    rosters: list[dict[str, Any]] | None,
    roster_profiles: dict[str, dict[str, Any]] | None,
    league_settings: dict[str, Any] | None,
    score_field: str,
    my_roster_id: Any = None,
    previous_ranks: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Rank complete rosters: existing players plus drafted players, with no extra youth bonus."""
    rosters = rosters or []
    roster_profiles = roster_profiles or {}
    settings = league_settings or {}
    if not rosters:
        return pd.DataFrame()
    players = (
        df_players.loc[:, ~df_players.columns.duplicated(keep="last")].copy()
        if df_players is not None else pd.DataFrame()
    )
    score_field = resolve_draft_board_score_field(players, score_field, settings)
    existing_by_roster: dict[int, set[str]] = {}
    for roster in rosters:
        roster_id = safe_int(roster.get("roster_id"), 0)
        if not roster_id:
            continue
        roster_players = roster.get("players") if isinstance(roster.get("players"), list) else []
        existing_by_roster[roster_id] = {safe_text(player_id) for player_id in roster_players if safe_text(player_id)}
    drafted_by_roster: dict[int, set[str]] = {roster_id: set() for roster_id in existing_by_roster}
    for pick in picks or []:
        roster_id = pick_roster_id(pick)
        player_id = pick_player_id(pick)
        if roster_id and player_id:
            drafted_by_roster.setdefault(roster_id, set()).add(player_id)

    relevant_player_ids = set().union(*existing_by_roster.values(), *drafted_by_roster.values())
    relevant_players = players
    if relevant_player_ids and "player_id" in players.columns:
        relevant_players = players[players["player_id"].astype(str).isin(relevant_player_ids)]
    values: dict[str, float] = {}
    names: dict[str, str] = {}
    positions: dict[str, str] = {}
    if not relevant_players.empty and "player_id" in relevant_players.columns:
        value_source = (
            relevant_players[score_field]
            if score_field in relevant_players.columns
            else pd.Series(0.0, index=relevant_players.index)
        )
        numeric_values = pd.to_numeric(value_source, errors="coerce").fillna(0.0)
        for row, numeric_value in zip(relevant_players.to_dict("records"), numeric_values.tolist()):
            player_id = safe_text(row.get("player_id"))
            if not player_id:
                continue
            values[player_id] = float(numeric_value)
            names[player_id] = safe_text(row.get("name"), "Player")
            positions[player_id] = safe_text(row.get("position"), "UNK").upper()

    qb_slots = max(1, safe_int(settings.get("qb_slots"), 1))
    rb_slots = max(1, safe_int(settings.get("rb_slots"), 2))
    wr_slots = max(1, safe_int(settings.get("wr_slots"), 2))
    te_slots = max(1, safe_int(settings.get("te_slots"), 1))
    flex_slots = max(0, safe_int(settings.get("flex_slots"), 1))
    superflex_slots = max(0, safe_int(settings.get("superflex_slots"), 0))
    raw_rows: list[dict[str, Any]] = []
    for roster_id in sorted(set(existing_by_roster) | set(drafted_by_roster)):
        existing_ids = existing_by_roster.get(roster_id, set())
        drafted_ids = drafted_by_roster.get(roster_id, set())
        player_ids = existing_ids | drafted_ids
        by_position: dict[str, list[float]] = {}
        for player_id in player_ids:
            by_position.setdefault(positions.get(player_id, "UNK"), []).append(values.get(player_id, 0.0))
        for position_values in by_position.values():
            position_values.sort(reverse=True)

        selected: list[float] = []
        leftovers: list[tuple[str, float]] = []
        for position, slot_count in (("QB", qb_slots), ("RB", rb_slots), ("WR", wr_slots), ("TE", te_slots)):
            position_values = by_position.get(position, [])
            selected.extend(position_values[:slot_count])
            leftovers.extend((position, value) for value in position_values[slot_count:])
        flex_eligible = sorted(
            [value for position, value in leftovers if position in {"RB", "WR", "TE"}],
            reverse=True,
        )
        selected.extend(flex_eligible[:flex_slots])
        used_flex = flex_eligible[:flex_slots]
        superflex_eligible = sorted(
            [value for position, value in leftovers if position == "QB"]
            + [value for value in flex_eligible if value not in used_flex],
            reverse=True,
        )
        selected.extend(superflex_eligible[:superflex_slots])

        total = sum(values.get(player_id, 0.0) for player_id in player_ids)
        starter_value = sum(selected)
        depth_value = max(0.0, total - starter_value)
        position_counts = Counter(positions.get(player_id, "UNK") for player_id in player_ids)
        required_covered = sum(
            min(position_counts.get(position, 0), required)
            for position, required in (("QB", qb_slots), ("RB", rb_slots), ("WR", wr_slots), ("TE", te_slots))
        )
        required_total = qb_slots + rb_slots + wr_slots + te_slots
        construction = 100.0 * required_covered / max(required_total, 1)
        top_id = max(player_ids, key=lambda player_id: values.get(player_id, 0.0), default="")
        profile = roster_profiles.get(str(roster_id), {})
        raw_rows.append({
            "roster_id": roster_id,
            "team_name": safe_text(profile.get("team_name") or profile.get("owner_name"), f"Roster {roster_id}"),
            "owner_name": safe_text(profile.get("owner_name")),
            "pick_count": len(drafted_ids),
            "roster_count": len(player_ids),
            "existing_count": len(existing_ids),
            "total_value": total,
            "starter_value": starter_value,
            "depth_value": depth_value,
            "average_value": total / len(player_ids) if player_ids else 0.0,
            "construction_score": construction,
            "top_player": names.get(top_id, "No players yet"),
            "positions": " · ".join(f"{pos} {count}" for pos, count in position_counts.most_common()) or "No players yet",
            "is_mine": str(roster_id) == str(my_roster_id),
            "score_field_used": score_field,
        })
    board = pd.DataFrame(raw_rows)

    def percentile(series: pd.Series) -> pd.Series:
        if series.nunique(dropna=False) <= 1:
            return pd.Series(50.0, index=series.index)
        return series.rank(method="average", pct=True) * 100.0

    board["live_team_score"] = (
        percentile(board["starter_value"]) * 0.60
        + percentile(board["total_value"]) * 0.30
        + percentile(board["depth_value"]) * 0.07
        + board["construction_score"] * 0.03
    )
    board = board.sort_values(
        ["live_team_score", "starter_value", "total_value", "team_name"],
        ascending=[False, False, False, True],
        kind="stable",
    ).reset_index(drop=True)
    board["team_rank"] = range(1, len(board) + 1)
    previous_ranks = previous_ranks or {}
    board["movement"] = [
        previous_ranks.get(str(row.get("roster_id")), safe_int(row.get("team_rank"), 0))
        - safe_int(row.get("team_rank"), 0)
        for _, row in board.iterrows()
    ]
    board["trend_label"] = ""
    if len(board):
        board.loc[0, "trend_label"] = "Best Team"
    if len(board) > 1:
        starter_idx = board["starter_value"].idxmax()
        if not board.loc[starter_idx, "trend_label"]:
            board.loc[starter_idx, "trend_label"] = "Best Starters"
    if len(board) > 2:
        depth_idx = board["depth_value"].idxmax()
        if not board.loc[depth_idx, "trend_label"]:
            board.loc[depth_idx, "trend_label"] = "Best Depth"
    return board

def preserve_last_valid_board(
    current_board: pd.DataFrame | None,
    last_valid_board: pd.DataFrame | None,
    *,
    api_error: bool,
) -> pd.DataFrame:
    if api_error and last_valid_board is not None and not last_valid_board.empty:
        return last_valid_board.copy()
    return current_board.copy() if current_board is not None else pd.DataFrame()


def positional_run_summary(pick_rows: list[dict[str, Any]], window: int = 8) -> str:
    recent = pick_rows[-window:]
    if not recent:
        return "No picks logged yet."
    counts = Counter(safe_text(row.get("position"), "UNK") for row in recent)
    return " | ".join(f"{pos} {count}" for pos, count in counts.most_common())


def draft_state_signature(picks: list[dict[str, Any]], draft: dict[str, Any] | None = None) -> str:
    """Opaque recomputation fingerprint that is never exposed in diagnostics."""
    safe_picks = [
        (
            safe_int(pick.get("pick_no"), 0),
            safe_text(pick.get("player_id")),
            safe_int(pick.get("roster_id"), 0),
        )
        for pick in (picks or [])
        if isinstance(pick, dict)
    ]
    draft_data = draft if isinstance(draft, dict) else {}
    payload = {
        "picks": safe_picks,
        "status": normalize_draft_status(draft_data.get("status")),
        "settings": draft_data.get("settings") if isinstance(draft_data.get("settings"), dict) else {},
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:20]


def build_live_draft_state(
    *,
    draft: dict[str, Any],
    picks: list[dict[str, Any]],
    df_players: pd.DataFrame,
    roster_df: pd.DataFrame,
    roster_profiles: dict[str, dict[str, Any]],
    rosters: list[dict[str, Any]],
    my_roster_id: Any,
    league_settings: dict[str, Any],
    score_field: str,
    previous_ranks: dict[str, int] | None = None,
    previous_team_ranks: dict[str, int] | None = None,
) -> dict[str, Any]:
    status = normalize_draft_status(draft.get("status"))
    rounds = draft_round_count(draft)
    teams = draft_team_count(draft, rosters)
    order_maps = build_draft_order_maps(draft, rosters)
    my_slot = safe_int(order_maps["roster_to_slot"].get(safe_int(my_roster_id, 0)), 0)
    next_pick = current_pick_number(picks)
    settings = draft.get("settings") if isinstance(draft.get("settings"), dict) else {}
    snake = safe_text(settings.get("type") or draft.get("type"), "snake").casefold() != "linear"
    current_slot = draft_slot_for_pick(next_pick, teams, snake=snake)
    current_roster = order_maps["slot_to_roster"].get(current_slot, 0)
    pick_rows = enrich_pick_rows(picks, df_players=df_players, roster_profiles=roster_profiles, my_roster_id=my_roster_id)
    pool = available_player_pool(df_players, picks, score_field=score_field)
    picks_away = picks_until_next_selection(current_pick=next_pick, my_slot=my_slot, team_count=teams, rounds=rounds, snake=snake)
    with performance.time_block("live_draft_player_rankings", category="analysis"):
        rankings = build_live_draft_rankings(
            pool,
            roster_df=roster_df,
            league_settings=league_settings,
            score_field=score_field,
            draft=draft,
            picks_until_mine=picks_away,
            previous_ranks=previous_ranks,
        )
    with performance.time_block("live_draft_team_rankings", category="analysis"):
        team_rankings = build_live_team_rankings(
            picks,
            df_players=df_players,
            rosters=rosters,
            roster_profiles=roster_profiles,
            league_settings=league_settings,
            score_field=score_field,
            my_roster_id=my_roster_id,
            previous_ranks=previous_team_ranks,
        )
    recs = build_live_draft_recommendations(
        pool,
        roster_df=roster_df,
        league_settings=league_settings,
        score_field=score_field,
    )
    return {
        "status": status,
        "rounds": rounds,
        "teams": teams,
        "picks_made": len(picks or []),
        "current_pick": next_pick,
        "current_slot": current_slot,
        "current_roster_id": current_roster,
        "current_team_name": safe_text((roster_profiles.get(str(current_roster)) or {}).get("team_name"), f"Roster {current_roster}" if current_roster else "Unknown Team"),
        "my_slot": my_slot,
        "is_my_pick": bool(my_slot and current_slot == my_slot and status in {"drafting", "paused"}),
        "picks_until_mine": picks_away,
        "pick_rows": pick_rows,
        "available_pool": pool,
        "rankings": rankings,
        "team_rankings": team_rankings,
        "recommendations": recs,
        "positional_run": positional_run_summary(pick_rows),
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
