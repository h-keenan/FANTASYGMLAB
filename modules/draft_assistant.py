from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Iterable

import pandas as pd

from modules import sleeper
from modules.platforms.sleeper import get_sleeper_adapter
from modules.player_eligibility import filter_current_fantasy_players
from modules.player_identity import ensure_identity_columns
from modules.roster_needs import true_roster_needs


CORE_DRAFT_POSITIONS = ("QB", "RB", "WR", "TE", "K")
RECOMMENDATION_BUCKETS = (
    "Best Overall",
    "Best Value",
    "Best Team Fit",
    "Best Positional Fit",
    "Safest Pick",
    "Upside Pick",
    "Avoid / Reach Warning",
)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    return text if text else default


def normalize_player_id(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except (TypeError, ValueError):
        pass
    return text


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if pd.notna(number) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


def normalize_draft_status(status: Any) -> str:
    text = _safe_text(status).strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"complete", "completed", "done", "finished", "closed"}:
        return "complete"
    if text in {"drafting", "in_progress", "inprogress", "started"}:
        return "in_progress"
    if text in {"pre_draft", "predraft", "scheduled", "setup"}:
        return "pre_draft"
    if text == "paused":
        return "paused"
    return text or "unknown"


def draft_status_label(status: Any) -> str:
    normalized = normalize_draft_status(status)
    return {
        "complete": "Complete",
        "in_progress": "In Progress",
        "pre_draft": "Not Started",
        "paused": "Paused",
        "unknown": "Unknown",
    }.get(normalized, normalized.replace("_", " ").title())


def is_completed_draft_status(status: Any) -> bool:
    return normalize_draft_status(status) == "complete"


def should_render_active_draft_sections(context: dict | None) -> bool:
    context = context if isinstance(context, dict) else {}
    return not (
        bool(context.get("review_mode"))
        or is_completed_draft_status(context.get("draft_status"))
    )


def draft_round_count(draft: dict | None) -> int:
    draft = draft if isinstance(draft, dict) else {}
    settings = draft.get("settings") if isinstance(draft.get("settings"), dict) else {}
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    return max(
        0,
        _safe_int(
            settings.get("rounds")
            or settings.get("round_count")
            or metadata.get("rounds")
            or draft.get("rounds"),
            0,
        ),
    )


def draft_pick_player_id(pick: dict | None) -> str:
    pick = pick if isinstance(pick, dict) else {}
    metadata = pick.get("metadata") if isinstance(pick.get("metadata"), dict) else {}
    return normalize_player_id(
        pick.get("player_id")
        or pick.get("sleeper_id")
        or metadata.get("player_id")
        or metadata.get("picked_player_id")
        or metadata.get("drafted_player_id")
        or metadata.get("sleeper_id")
        or metadata.get("sleeper_player_id")
        or metadata.get("playerId")
    )


def normalize_player_name(value: Any) -> str:
    text = _safe_text(value).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def draft_pick_player_name(pick: dict | None) -> str:
    pick = pick if isinstance(pick, dict) else {}
    metadata = pick.get("metadata") if isinstance(pick.get("metadata"), dict) else {}
    full_name = _safe_text(
        metadata.get("full_name")
        or metadata.get("player_name")
        or metadata.get("name")
        or pick.get("player_name")
    )
    if full_name:
        return full_name
    first = _safe_text(metadata.get("first_name") or pick.get("first_name"))
    last = _safe_text(metadata.get("last_name") or pick.get("last_name"))
    return " ".join(part for part in (first, last) if part).strip()


def draft_pick_roster_id(pick: dict | None) -> int:
    pick = pick if isinstance(pick, dict) else {}
    metadata = pick.get("metadata") if isinstance(pick.get("metadata"), dict) else {}
    return _safe_int(
        pick.get("roster_id")
        or metadata.get("roster_id")
        or metadata.get("owner_id"),
        0,
    )


def infer_my_draft_slot(draft: dict | None, my_roster_id: int | None) -> int:
    if my_roster_id is None:
        return 0
    draft = draft if isinstance(draft, dict) else {}
    draft_order = draft.get("draft_order") if isinstance(draft.get("draft_order"), dict) else {}
    direct_slot = _safe_int(draft_order.get(str(my_roster_id)) or draft_order.get(my_roster_id), 0)
    if direct_slot:
        return direct_slot
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    slot_map = metadata.get("slot_to_roster_id") if isinstance(metadata.get("slot_to_roster_id"), dict) else {}
    for slot_key, roster_value in slot_map.items():
        if str(roster_value) == str(my_roster_id):
            return _safe_int(slot_key, 0)
    return 0


def pick_label(pick: dict | None) -> str:
    pick = pick if isinstance(pick, dict) else {}
    round_no = _safe_int(pick.get("round"), 0)
    pick_no = _safe_int(pick.get("pick_no") or pick.get("pick") or pick.get("draft_slot"), 0)
    overall = _safe_int(pick.get("pick_no") or pick.get("overall_pick") or pick.get("pick"), 0)
    if round_no and pick_no:
        return f"Round {round_no}, Pick {pick_no}"
    if overall:
        return f"Pick {overall}"
    return "Unknown pick"


def draft_pick_overall_number(pick: dict | None) -> int:
    pick = pick if isinstance(pick, dict) else {}
    return _safe_int(
        pick.get("pick_no")
        or pick.get("overall_pick")
        or pick.get("pick")
        or pick.get("draft_slot"),
        0,
    )


def group_picks_by_round(picks: Iterable[dict] | None) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for pick in picks or []:
        round_no = _safe_int((pick or {}).get("round"), 0)
        grouped.setdefault(round_no or 0, []).append(pick)
    for round_no, round_picks in grouped.items():
        grouped[round_no] = sorted(
            round_picks,
            key=lambda item: draft_pick_overall_number(item) or 9999,
        )
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


def grade_completed_draft_pick(
    player_row: pd.Series | dict | None,
    *,
    pick_number: int,
    value_rank: int | None = None,
    score_field: str = "value_score",
) -> tuple[str, str]:
    if player_row is None:
        return "Ungraded", "Unmatched Sleeper player; grade unavailable."
    row = player_row if isinstance(player_row, (pd.Series, dict)) else {}
    value = _safe_float(row.get(score_field, row.get("value_score")), 0.0)
    if value <= 0:
        return "Ungraded", "No player value available."

    pick = max(int(pick_number or 1), 1)
    rank = int(value_rank or pick)
    value_edge = pick - rank

    if rank == 1:
        if pick == 1:
            return "A", "Best available on the board."
        if pick >= 8:
            return "A+", "Major value fall versus slot."
        return "A", "Best remaining player at this slot."

    if pick <= 3:
        if rank <= 3:
            return "A-", "Top-tier value at this slot."
        if rank <= 5:
            return "B+", "Acceptable value in this range."
        if rank <= 8:
            return "B", "Fair value for this slot."
    if rank <= 3 and pick >= 10:
        return "A+", "Elite value versus slot."
    if rank <= 2 and pick >= 5:
        return "A", "Strong value versus slot."
    if value_edge >= 24:
        return "A+", "Elite value versus slot."
    if value_edge >= 14:
        return "A", "Strong value versus slot."
    if value_edge >= 7:
        return "A-", "Good value versus slot."
    if value_edge >= 2:
        return "B+", "Solid pick with modest value."
    if value_edge >= -2:
        return "B+", "Acceptable value in this range."
    if value_edge >= -5:
        return "B-", "Slight reach compared with available board."
    if value_edge >= -9:
        return "C+", "Slight reach compared with board."
    if value_edge >= -14:
        return "C", "Reach versus available value."
    if value_edge >= -24:
        return "D", "Large value gap at this slot."
    return "F", "Severe value gap at this slot."


def remaining_board_rank(
    player_id: Any,
    ranked_player_ids: list[str],
    drafted_ids: set[str] | None = None,
) -> int | None:
    target = normalize_player_id(player_id)
    if not target:
        return None
    drafted = {normalize_player_id(value) for value in (drafted_ids or set()) if normalize_player_id(value)}
    rank = 0
    for candidate_id in ranked_player_ids or []:
        candidate = normalize_player_id(candidate_id)
        if not candidate or candidate in drafted:
            continue
        rank += 1
        if candidate == target:
            return rank
    return None


def completed_pick_review_rows(
    picks: Iterable[dict] | None,
    df_players: pd.DataFrame,
    *,
    score_field: str = "value_score",
    my_roster_id: int | None = None,
) -> list[dict]:
    id_column = player_id_column(df_players)
    player_lookup: dict[str, pd.Series] = {}
    ranked_player_ids: list[str] = []
    if id_column and df_players is not None and not df_players.empty:
        ranked = df_players.copy()
        ranked["_draft_review_value"] = pd.to_numeric(
            ranked.get(score_field, ranked.get("value_score", 0)),
            errors="coerce",
        ).fillna(0)
        ranked = ranked.sort_values("_draft_review_value", ascending=False).reset_index(drop=True)
        for _, row in ranked.iterrows():
            normalized_id = normalize_player_id(row.get(id_column))
            if normalized_id:
                ranked_player_ids.append(normalized_id)
        for _, row in df_players.iterrows():
            player_lookup[normalize_player_id(row.get(id_column))] = row

    rows: list[dict] = []
    drafted_ids: set[str] = set()
    ordered_picks = sorted(
        list(picks or []),
        key=lambda item: draft_pick_overall_number(item) or 9999,
    )
    for pick in ordered_picks:
        player_id = draft_pick_player_id(pick)
        row = player_lookup.get(player_id)
        pick_number = draft_pick_overall_number(pick)
        pick_relative_rank = remaining_board_rank(
            player_id,
            ranked_player_ids,
            drafted_ids,
        )
        grade, reason = grade_completed_draft_pick(
            row,
            pick_number=pick_number,
            value_rank=pick_relative_rank,
            score_field=score_field,
        )
        roster_id = draft_pick_roster_id(pick)
        rows.append(
            {
                "round": _safe_int((pick or {}).get("round"), 0),
                "pick_number": pick_number,
                "pick_label": pick_label(pick),
                "player_id": player_id,
                "player_name": (
                    _safe_text(row.get("name"))
                    if row is not None
                    else draft_pick_player_name(pick)
                ),
                "position": _safe_text(row.get("position")).upper() if row is not None else "",
                "team": _safe_text(row.get("team")).upper() if row is not None else "",
                "roster_id": roster_id,
                "is_my_pick": (
                    my_roster_id is not None
                    and roster_id == int(my_roster_id)
                ),
                "value": _safe_float(row.get(score_field, row.get("value_score")), 0.0)
                if row is not None
                else 0.0,
                "value_rank": pick_relative_rank or 0,
                "grade": grade,
                "grade_reason": reason,
                "matched": row is not None,
            }
        )
        if player_id:
            drafted_ids.add(player_id)
    return sorted(rows, key=lambda item: item.get("pick_number") or 9999)


def analyze_drafted_pick_matches(
    picks: Iterable[dict] | None,
    df_players: pd.DataFrame,
) -> dict:
    id_column = player_id_column(df_players)
    if df_players is None or df_players.empty or not id_column:
        player_ids: set[str] = set()
        name_lookup: dict[str, list[str]] = {}
    else:
        player_ids = {
            normalize_player_id(value)
            for value in df_players[id_column].tolist()
            if normalize_player_id(value)
        }
        name_lookup = {}
        if "name" in df_players.columns:
            for _, row in df_players.iterrows():
                normalized_name = normalize_player_name(row.get("name"))
                normalized_id = normalize_player_id(row.get(id_column))
                if normalized_name and normalized_id:
                    name_lookup.setdefault(normalized_name, []).append(normalized_id)

    id_matches: set[str] = set()
    fallback_matches: set[str] = set()
    unmatched: list[dict] = []

    for pick in picks or []:
        player_id = draft_pick_player_id(pick)
        if player_id and player_id in player_ids:
            id_matches.add(player_id)
            continue
        player_name = draft_pick_player_name(pick)
        normalized_name = normalize_player_name(player_name)
        candidates = sorted(set(name_lookup.get(normalized_name, []))) if normalized_name else []
        if len(candidates) == 1:
            fallback_matches.add(candidates[0])
            continue
        unmatched.append(
            {
                "pick": pick_label(pick),
                "round": _safe_int((pick or {}).get("round"), 0),
                "roster_id": draft_pick_roster_id(pick),
                "raw_player_id": player_id,
                "player_name": player_name,
                "reason": (
                    "Ambiguous metadata name match"
                    if len(candidates) > 1
                    else "No matching app player ID or exact metadata name"
                ),
            }
        )

    return {
        "id_matched_ids": sorted(id_matches),
        "fallback_matched_ids": sorted(fallback_matches),
        "matched_ids": sorted(id_matches | fallback_matches),
        "unmatched_picks": unmatched,
        "id_match_count": len(id_matches),
        "fallback_match_count": len(fallback_matches),
        "unmatched_count": len(unmatched),
    }


def infer_upcoming_pick_numbers(
    draft: dict | None,
    *,
    my_roster_id: int | None,
    league_size: int,
    rounds: int,
    picks_made: int,
    limit: int = 3,
) -> list[int]:
    my_slot = infer_my_draft_slot(draft, my_roster_id)
    if not my_slot or league_size <= 0 or rounds <= 0:
        return []
    draft = draft if isinstance(draft, dict) else {}
    settings = draft.get("settings") if isinstance(draft.get("settings"), dict) else {}
    draft_type = _safe_text(draft.get("type") or settings.get("type")).lower()
    snake = "snake" in draft_type
    upcoming: list[int] = []
    for round_number in range(1, int(rounds) + 1):
        slot = my_slot
        if snake and round_number % 2 == 0:
            slot = int(league_size) - int(my_slot) + 1
        pick_number = (round_number - 1) * int(league_size) + int(slot)
        if pick_number > int(picks_made):
            upcoming.append(pick_number)
        if len(upcoming) >= limit:
            break
    return upcoming


def clear_sleeper_draft_caches() -> None:
    for function_name in ("get_league_drafts", "get_draft", "get_draft_picks"):
        function = getattr(sleeper, function_name, None)
        cache_clear = getattr(function, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()


def draft_context_key(username: str, league_id: str, draft_id: str | None = None) -> str:
    user_key = _safe_text(username, "anonymous").casefold()
    league_key = _safe_text(league_id, "no_league")
    draft_key = _safe_text(draft_id, "manual")
    return f"draft_assistant:{user_key}:{league_key}:{draft_key}"


def manual_drafted_state_key(username: str, league_id: str, draft_id: str | None = None) -> str:
    return draft_context_key(username, league_id, draft_id) + ":manual_drafted"


def refresh_timestamp_state_key(username: str, league_id: str, draft_id: str | None = None) -> str:
    return draft_context_key(username, league_id, draft_id) + ":last_refresh"


def normalize_manual_ids(values: Iterable[Any] | None) -> list[str]:
    return sorted({normalize_player_id(value) for value in values or [] if normalize_player_id(value)})


def merge_drafted_ids(live_ids: Iterable[Any] | None, manual_ids: Iterable[Any] | None) -> set[str]:
    return {
        normalize_player_id(value)
        for value in list(live_ids or []) + list(manual_ids or [])
        if normalize_player_id(value)
    }


def fetch_league_draft_options(
    league_id: str,
    *,
    refresh: bool = False,
) -> list[dict]:
    if refresh:
        clear_sleeper_draft_caches()
    if not league_id:
        return []

    adapter = get_sleeper_adapter()
    options: list[dict] = []
    for draft_stub in adapter.get_league_drafts(str(league_id)) or []:
        draft_id = _safe_text(draft_stub.get("draft_id") or draft_stub.get("id"))
        draft = adapter.get_draft(draft_id) if draft_id else {}
        merged = dict(draft_stub or {})
        merged.update(draft or {})
        status = normalize_draft_status(merged.get("status"))
        rounds = draft_round_count(merged)
        season = _safe_int(merged.get("season"), datetime.now().year)
        start_time = _safe_int(merged.get("start_time"), 0)
        draft_type = _safe_text(merged.get("type") or merged.get("draft_type"))
        options.append(
            {
                "draft_id": draft_id,
                "draft": merged,
                "status": status,
                "status_label": draft_status_label(status),
                "rounds": rounds,
                "season": season,
                "start_time": start_time,
                "type": draft_type,
                "label": draft_option_label(merged, draft_id=draft_id),
            }
        )
    return sorted(options, key=draft_option_sort_key, reverse=True)


def draft_option_status_priority(status: Any) -> int:
    normalized = normalize_draft_status(status)
    if normalized in {"in_progress", "paused"}:
        return 4
    if normalized == "pre_draft":
        return 3
    if normalized == "complete":
        return 2
    return 1


def draft_option_sort_key(option: dict) -> tuple:
    return (
        draft_option_status_priority(option.get("status")),
        _safe_int(option.get("season"), 0),
        _safe_int(option.get("start_time"), 0),
        _safe_int(option.get("rounds"), 0),
        _safe_text(option.get("draft_id")),
    )


def select_default_draft_option(options: list[dict]) -> dict:
    if not options:
        return {}
    return sorted(options, key=draft_option_sort_key, reverse=True)[0]


def draft_option_label(draft: dict | None, *, draft_id: str = "") -> str:
    draft = draft if isinstance(draft, dict) else {}
    season = _safe_text(draft.get("season"), "Unknown season")
    status = draft_status_label(draft.get("status"))
    rounds = draft_round_count(draft)
    draft_type = _safe_text(draft.get("type") or draft.get("draft_type"))
    type_text = f" | {draft_type.title()}" if draft_type else ""
    id_text = _safe_text(draft_id or draft.get("draft_id") or draft.get("id"))
    suffix = f" | {id_text[-6:]}" if id_text else ""
    round_text = f"{rounds} rounds" if rounds else "rounds unknown"
    return f"{season} draft | {status} | {round_text}{type_text}{suffix}"


def build_live_draft_context(
    league_id: str,
    *,
    username: str = "",
    my_roster_id: int | None = None,
    selected_draft_id: str | None = None,
    refresh: bool = False,
) -> dict:
    adapter = get_sleeper_adapter()
    draft_options = fetch_league_draft_options(league_id, refresh=refresh)
    selected_id = _safe_text(selected_draft_id)
    selected = None
    if selected_id:
        selected = next(
            (option for option in draft_options if option.get("draft_id") == selected_id),
            None,
        )
    if selected is None and selected_id:
        draft = adapter.get_draft(selected_id)
        if draft:
            selected = {
                "draft_id": selected_id,
                "draft": draft,
                "status": normalize_draft_status(draft.get("status")),
                "status_label": draft_status_label(draft.get("status")),
                "rounds": draft_round_count(draft),
                "season": _safe_int(draft.get("season"), datetime.now().year),
                "start_time": _safe_int(draft.get("start_time"), 0),
                "type": _safe_text(draft.get("type") or draft.get("draft_type")),
                "label": draft_option_label(draft, draft_id=selected_id),
            }
    if selected is None and not selected_id and draft_options:
        selected = select_default_draft_option(draft_options)
        selected_id = _safe_text(selected.get("draft_id"))

    live_picks = adapter.get_draft_picks(selected_id) if selected_id else []
    live_drafted_ids = sorted(
        {
            player_id
            for player_id in (draft_pick_player_id(pick) for pick in live_picks)
            if player_id
        }
    )
    draft = (selected or {}).get("draft") or {}
    status = normalize_draft_status((selected or {}).get("status") or draft.get("status"))
    rounds = _safe_int((selected or {}).get("rounds"), draft_round_count(draft))
    is_completed = is_completed_draft_status(status)

    league = adapter.get_league(league_id) if league_id else {}
    rosters = adapter.get_rosters(league_id) if league_id else []
    league_size = max(
        len(rosters or []),
        _safe_int(((league or {}).get("settings") or {}).get("num_teams"), 0),
        _safe_int(((league or {}).get("settings") or {}).get("league_size"), 0),
    )
    total_picks = rounds * league_size if rounds and league_size else 0
    picks_made = len(live_picks or [])
    current_pick = picks_made + 1 if not total_picks or picks_made < total_picks else total_picks
    my_draft_slot = infer_my_draft_slot(draft, my_roster_id)
    my_upcoming_picks = infer_upcoming_pick_numbers(
        draft,
        my_roster_id=my_roster_id,
        league_size=league_size,
        rounds=rounds,
        picks_made=picks_made,
    )
    my_drafted_ids = sorted(
        {
            draft_pick_player_id(pick)
            for pick in live_picks or []
            if my_roster_id is not None
            and draft_pick_roster_id(pick) == int(my_roster_id)
            and draft_pick_player_id(pick)
        }
    )

    return {
        "league_id": league_id,
        "username": username,
        "draft_options": draft_options,
        "draft_count": len(draft_options),
        "draft_available": bool(selected_id),
        "selected_draft_id": selected_id,
        "selected_draft_label": (selected or {}).get("label", "Manual board"),
        "selected_draft_season": (selected or {}).get("season", ""),
        "selected_draft_type": (selected or {}).get("type", ""),
        "draft_status": status,
        "draft_status_label": draft_status_label(status),
        "is_completed": is_completed,
        "review_mode": is_completed,
        "draft_rounds": rounds,
        "league_size": league_size,
        "picks_made": picks_made,
        "total_picks": total_picks,
        "current_pick": current_pick,
        "my_draft_slot": my_draft_slot,
        "my_upcoming_picks": my_upcoming_picks,
        "live_picks": live_picks or [],
        "live_drafted_player_ids": live_drafted_ids,
        "my_drafted_player_ids": my_drafted_ids,
        "mode_label": (
            "Live Sleeper draft detected"
            if selected_id
            else "Manual mode"
        ),
    }


def build_available_player_pool(
    df_players: pd.DataFrame,
    drafted_player_ids: Iterable[Any] | None,
    *,
    score_field: str,
) -> pd.DataFrame:
    if df_players is None or df_players.empty:
        return pd.DataFrame()
    drafted_ids = merge_drafted_ids(drafted_player_ids, [])
    pool = filter_current_fantasy_players(
        ensure_identity_columns(df_players),
        surface="draft_assistant_available_pool",
    )
    id_column = player_id_column(pool)
    if id_column and drafted_ids:
        normalized_ids = pool[id_column].map(normalize_player_id)
        pool = pool[~normalized_ids.isin(drafted_ids)].copy()
    if "position" in pool.columns:
        pool = pool[
            pool["position"].fillna("").astype(str).str.upper().isin(CORE_DRAFT_POSITIONS)
        ].copy()
    if score_field not in pool.columns:
        score_field = "value_score" if "value_score" in pool.columns else pool.columns[0]
    pool["_draft_assistant_score"] = pd.to_numeric(
        pool.get(score_field),
        errors="coerce",
    ).fillna(0.0)
    return pool.sort_values(
        ["_draft_assistant_score", "market_score", "name"]
        if "market_score" in pool.columns
        else ["_draft_assistant_score", "name"],
        ascending=[False, False, True] if "market_score" in pool.columns else [False, True],
    ).reset_index(drop=True)


def player_id_column(df_players: pd.DataFrame) -> str:
    if df_players is None or df_players.empty:
        return ""
    for column in ("player_id", "canonical_player_id", "sleeper_id", "id"):
        if column in df_players.columns:
            return column
    return ""


def apply_draft_pool_filter(df_players: pd.DataFrame, draft_context: dict | None) -> pd.DataFrame:
    if df_players is None or df_players.empty:
        return pd.DataFrame()
    pool = filter_current_fantasy_players(
        df_players,
        surface="draft_assistant_pool_filter",
    )
    context = draft_context or {}
    rounds = _safe_int(context.get("draft_rounds"), 0)
    if rounds <= 0 or rounds > 6:
        return pool
    years_exp = pd.to_numeric(
        pool.get("years_exp", pd.Series(99, index=pool.index)),
        errors="coerce",
    ).fillna(99)
    ages = pd.to_numeric(
        pool.get("age", pd.Series(99, index=pool.index)),
        errors="coerce",
    ).fillna(99)
    if normalize_draft_status(context.get("draft_status")) == "complete":
        rookie_like = pool[years_exp <= 1].copy()
        if len(rookie_like) >= 20:
            return rookie_like
    rookie_like = pool[(years_exp <= 1) | ((years_exp <= 2) & (ages <= 24))].copy()
    return rookie_like if len(rookie_like) >= 20 else pool


def _player_note(row: pd.Series | dict, *, bucket: str, room_note: str = "") -> str:
    pos = _safe_text(row.get("position")).upper()
    tier = _safe_text(row.get("player_tier") or row.get("opportunity_label"))
    if bucket == "Best Overall":
        return f"Highest remaining board value at {pos}."
    if bucket == "Best Value":
        return f"Best value gap still available at {pos}."
    if bucket == "Best Team Fit":
        return room_note or f"Fits one of the roster rooms that still needs help."
    if bucket == "Best Positional Fit":
        return room_note or f"Position scarcity and team fit are both favorable."
    if bucket == "Safest Pick":
        return f"Strong value without a major injury flag."
    if bucket == "Upside Pick":
        return f"{tier or 'Upside'} profile with age/opportunity runway."
    return f"Potential reach unless your board specifically needs {pos}."


def _is_injury_flag(row: pd.Series | dict) -> bool:
    text = " ".join(
        _safe_text(row.get(field)).lower()
        for field in ("status", "injury_status", "injury_level")
    )
    return any(term in text for term in ("out", "ir", "pup", "questionable", "doubtful", "injur"))


def _effective_need_positions(needs: list[str], rooms: dict[str, dict[str, Any]]) -> list[str]:
    effective: list[str] = []
    for position in needs:
        position = _safe_text(position).upper()
        room = rooms.get(position) or {}
        required = _safe_int(room.get("required_starters"), 1)
        active_coverage = _safe_int(room.get("active_coverage_count"), 0)
        future_coverage = _safe_int(room.get("future_coverage_count"), 0)
        playable_backups = len(room.get("playable_backups") or [])
        future_depth = len(room.get("developmental_depth_assets") or [])
        if position == "QB" and not bool(room.get("superflex")):
            if active_coverage >= 1 and (playable_backups or future_depth or future_coverage):
                continue
        if position == "TE" and active_coverage >= required and future_coverage:
            continue
        if active_coverage >= required and not room.get("long_term_need"):
            continue
        if position not in effective:
            effective.append(position)
    return effective


def _dedupe_bucket_rows(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        key = _safe_text(item.get("bucket"))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_recommendation_buckets(
    available_pool: pd.DataFrame,
    *,
    roster_df: pd.DataFrame | None = None,
    lineup_df: pd.DataFrame | None = None,
    league_settings: dict | None = None,
    score_field: str = "value_score",
    limit: int = 7,
) -> list[dict]:
    if available_pool is None or available_pool.empty:
        return []
    board = filter_current_fantasy_players(
        available_pool,
        surface="draft_assistant_recommendations",
    ).reset_index(drop=True)
    if board.empty:
        return []
    if score_field not in board.columns:
        score_field = "value_score" if "value_score" in board.columns else "_draft_assistant_score"
    board["_score"] = pd.to_numeric(board.get(score_field), errors="coerce").fillna(0.0)
    board["_market"] = pd.to_numeric(board.get("market_score", board["_score"]), errors="coerce").fillna(0.0)
    board["_scarcity"] = pd.to_numeric(board.get("scarcity_score", 0), errors="coerce").fillna(0.0)
    board["_age"] = pd.to_numeric(board.get("age", 99), errors="coerce").fillna(99.0)

    needs: list[str] = []
    rooms: dict[str, dict[str, Any]] = {}
    if roster_df is not None and not roster_df.empty:
        baseline = []
        for position in ("QB", "RB", "WR", "TE"):
            position_count = int(
                (
                    roster_df.get("position", pd.Series("", index=roster_df.index))
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    == position
                ).sum()
            )
            if position_count <= 1:
                baseline.append(position)
        needs, rooms = true_roster_needs(roster_df, lineup_df, league_settings or {}, baseline)

    items: list[dict] = []
    used_player_ids: set[str] = set()

    def add_bucket(bucket: str, row: pd.Series | dict, reason: str, *, allow_duplicate: bool = False) -> None:
        player_id = normalize_player_id(row.get("player_id") or row.get("sleeper_id") or row.get("id"))
        if player_id and player_id in used_player_ids and not allow_duplicate:
            return
        if player_id:
            used_player_ids.add(player_id)
        items.append(
            {
                "bucket": bucket,
                "player": dict(row),
                "reason": reason,
            }
        )

    def first_unused(frame: pd.DataFrame) -> pd.Series | None:
        for _, row in frame.iterrows():
            player_id = normalize_player_id(row.get("player_id") or row.get("sleeper_id") or row.get("id"))
            if not player_id or player_id not in used_player_ids:
                return row
        return None

    best_overall = board.iloc[0]
    add_bucket("Best Overall", best_overall, _player_note(best_overall, bucket="Best Overall"))

    value_board = board.assign(_value_gap=board["_score"] - (board["_market"] * 0.9))
    best_value = first_unused(value_board.sort_values(["_value_gap", "_score"], ascending=[False, False]))
    if best_value is not None:
        add_bucket("Best Value", best_value, _player_note(best_value, bucket="Best Value"))

    need_positions = [
        position
        for position in _effective_need_positions(needs, rooms)
        if position in {"QB", "RB", "WR", "TE"}
    ]
    need_board = board[board["position"].fillna("").astype(str).str.upper().isin(need_positions)].copy()
    if not need_board.empty:
        best_fit = first_unused(need_board)
        allow_duplicate_fit = False
        if best_fit is None:
            best_fit = need_board.iloc[0]
            allow_duplicate_fit = True
        pos = _safe_text(best_fit.get("position")).upper()
        room_note = _safe_text((rooms.get(pos) or {}).get("need_type"))
        add_bucket(
            "Best Team Fit",
            best_fit,
            _player_note(best_fit, bucket="Best Team Fit", room_note=room_note),
            allow_duplicate=allow_duplicate_fit,
        )
        positional_board = need_board.assign(
            _fit_score=need_board["_score"] + need_board["_scarcity"] * 12
        ).sort_values(["_fit_score", "_score"], ascending=[False, False])
        positional = first_unused(positional_board)
        if positional is not None:
            pos = _safe_text(positional.get("position")).upper()
            room_note = _safe_text((rooms.get(pos) or {}).get("need_type"))
            add_bucket(
                "Best Positional Fit",
                positional,
                _player_note(positional, bucket="Best Positional Fit", room_note=room_note),
            )

    safe_board = board[~board.apply(_is_injury_flag, axis=1)].copy()
    if not safe_board.empty:
        safe_pick = first_unused(safe_board)
        if safe_pick is not None:
            add_bucket("Safest Pick", safe_pick, _player_note(safe_pick, bucket="Safest Pick"))

    upside_board = board[
        (board["_age"] <= 25)
        | board.get("opportunity_label", pd.Series("", index=board.index))
        .fillna("")
        .astype(str)
        .str.lower()
        .str.contains("elite|strong|upside|rising", regex=True)
    ].copy()
    if not upside_board.empty:
        upside_pick = first_unused(upside_board.sort_values(["_score", "_age"], ascending=[False, True]))
        if upside_pick is not None:
            add_bucket("Upside Pick", upside_pick, _player_note(upside_pick, bucket="Upside Pick"))

    leader_score = _safe_float(best_overall.get("_score"), 0.0)
    if need_positions:
        reach_candidates = board[
            board["position"].fillna("").astype(str).str.upper().isin(need_positions)
        ].copy()
        if not reach_candidates.empty:
            reach = reach_candidates.iloc[0]
            if leader_score and _safe_float(reach.get("_score"), 0.0) < leader_score * 0.82:
                add_bucket(
                    "Avoid / Reach Warning",
                    reach,
                    (
                        f"{_safe_text(reach.get('position')).upper()} fits a need, "
                        "but the value gap to the top board is large."
                    ),
                )

    return _dedupe_bucket_rows(items)[: max(1, int(limit))]
