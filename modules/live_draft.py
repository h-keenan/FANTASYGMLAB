"""Read-only Sleeper live draft helpers."""

from __future__ import annotations

from collections import Counter
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


def positional_run_summary(pick_rows: list[dict[str, Any]], window: int = 8) -> str:
    recent = pick_rows[-window:]
    if not recent:
        return "No picks logged yet."
    counts = Counter(safe_text(row.get("position"), "UNK") for row in recent)
    return " | ".join(f"{pos} {count}" for pos, count in counts.most_common())


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
        "picks_until_mine": picks_until_next_selection(current_pick=next_pick, my_slot=my_slot, team_count=teams, rounds=rounds, snake=snake),
        "pick_rows": pick_rows,
        "available_pool": pool,
        "recommendations": recs,
        "positional_run": positional_run_summary(pick_rows),
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
