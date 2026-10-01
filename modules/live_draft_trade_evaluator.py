"""Live draft-pick trade evaluator: hypothetical trade math for an active
Sleeper live draft (rookie draft or startup draft currently in progress).

This module intentionally invents NO new valuation or verdict logic. Every
number comes from the exact same primitives the standalone Trade Calculator
(Trade Analyzer) already uses:

- Player value: ``modules.trade_analyzer_assembly.player_asset_from_mapping``
  copies an already-loaded ``df_players`` row's ``value_score``/``score``
  straight through (same helper the Trade Analyzer catalog uses). It is
  never recomputed here, and this module never calls
  ``rankings.load_players``/``build_players_table`` — the caller must pass
  an already-loaded ``df_players``.
- Pick value (not yet made): ``modules.trade_ideas.list_draft_pick_assets``
  is the app's one pick-pricing engine. Per that module (and its tests),
  pricing is ROUND-level — there is no overall-pick-slot ("1.08") concept
  anywhere in the app. This module matches a live draft's round + slot to
  the matching ``(season, round, original_roster_id)`` entry in that list
  and uses its ``score`` verbatim. The pick's *label* is enriched with the
  real slot number the live draft board already knows (e.g.
  "2026 Round 1 (Pick 1.08)") — that is presentation only, not a different
  valuation. When no matching scored asset exists (e.g. a startup draft
  with no rostered players yet to price team strength from), this falls
  back to ``modules.league_rankings.safe_pick_value``'s existing static
  round->value chart — the app's own pre-existing fallback, not an
  invented number.
- Verdict: ``modules.trade_analyzer_fit.score_asset_value`` /
  ``trade_value_verdict`` (itself ``modules.trade_visual_language.
  trade_value_band``) — the same Favorable / Fair / Slight Overpay / Major
  Overpay banding used everywhere else in the app.

This module has no Streamlit dependency so it can be unit tested directly.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules import live_draft
from modules.league_rankings import safe_pick_value
from modules.trade_analyzer_assembly import player_asset_from_mapping
from modules.trade_analyzer_fit import score_asset_value, trade_value_verdict


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def remaining_pick_options(
    *,
    draft: Mapping[str, Any] | None,
    rosters: Sequence[Mapping[str, Any]] | None,
    picks: Sequence[Mapping[str, Any]] | None,
    rounds: int,
    teams: int,
    roster_profiles: Mapping[Any, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Every pick slot in this draft room that has NOT been made yet.

    Each option carries a stable ``pick_key`` (derived from the overall
    pick number) used by :func:`validate_pick_keys_still_open` to detect
    a pick that got drafted by someone else between when the user opened
    the evaluator and when they submit it.
    """

    draft = draft if isinstance(draft, Mapping) else {}
    rosters = list(rosters or [])
    teams = int(teams or 0)
    rounds = int(rounds or 0)
    if teams <= 0 or rounds <= 0:
        return []

    maps = live_draft.build_draft_order_maps(dict(draft), rosters)
    slot_to_roster = maps.get("slot_to_roster", {})
    made_pick_numbers = {
        live_draft.pick_number(pick) for pick in (picks or []) if live_draft.pick_number(pick) > 0
    }
    profiles = roster_profiles or {}

    options: list[dict[str, Any]] = []
    for pick_no in range(1, rounds * teams + 1):
        if pick_no in made_pick_numbers:
            continue
        slot = live_draft.draft_slot_for_pick(pick_no, teams, snake=True)
        if not slot:
            continue
        round_no = (pick_no - 1) // teams + 1
        roster_id = slot_to_roster.get(slot, 0)
        profile = profiles.get(str(roster_id)) or profiles.get(roster_id) or {}
        team_name = str(
            profile.get("team_name")
            or profile.get("username")
            or (f"Team {roster_id}" if roster_id else "Unassigned slot")
        )
        round_pick = f"{round_no}.{slot:02d}"
        options.append(
            {
                "pick_key": f"pick:{pick_no}",
                "pick_no": pick_no,
                "round": round_no,
                "draft_slot": slot,
                "round_pick": round_pick,
                "original_roster_id": roster_id,
                "team_name": team_name,
                "label": f"Pick {round_pick} · Rd {round_no} · {team_name}",
            }
        )
    return options


def validate_pick_keys_still_open(
    pick_keys: Sequence[str],
    *,
    open_options: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Return the subset of ``pick_keys`` that are no longer open.

    Used right before computing a verdict so a pick someone else selected
    mid-evaluation never silently misvalues the trade — the caller should
    block evaluation and ask the user to re-pick when this is non-empty.
    """

    open_keys = {str(option.get("pick_key")) for option in open_options}
    return [str(key) for key in pick_keys if str(key) not in open_keys]


def pick_asset_for_option(
    option: Mapping[str, Any],
    *,
    season: int,
    draft_pick_assets: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Build a trade-package pick asset for a not-yet-made live-draft pick.

    Looks up the real score from ``draft_pick_assets`` — the exact list
    ``modules.trade_ideas.list_draft_pick_assets`` already produces for
    this league — by ``(season, round, original_roster_id)``. Falls back
    to ``modules.league_rankings.safe_pick_value``'s static round chart
    only when no matching priced asset exists.
    """

    round_no = _safe_int(option.get("round"))
    original_roster_id = option.get("original_roster_id")
    season = int(season or 0)

    match: Mapping[str, Any] | None = None
    for asset in draft_pick_assets or []:
        if not isinstance(asset, Mapping):
            continue
        if asset.get("asset_type") != "pick":
            continue
        if _safe_int(asset.get("season")) != season:
            continue
        if _safe_int(asset.get("round")) != round_no:
            continue
        asset_original = asset.get("original_roster_id", asset.get("owner_roster_id"))
        if str(asset_original) == str(original_roster_id):
            match = asset
            break

    round_pick = option.get("round_pick") or str(round_no)
    team_name = option.get("team_name") or ""

    if match is not None:
        score = _safe_int(match.get("score"))
        owner_roster_id = match.get("owner_roster_id", original_roster_id)
        owner_team_name = match.get("owner_team_name", team_name)
        pick_source = "modeled"
    else:
        # Existing app-wide fallback (modules.league_rankings.safe_pick_value's
        # static round->value chart) — not a new number invented here.
        score = safe_pick_value({"round": round_no})
        owner_roster_id = original_roster_id
        owner_team_name = team_name
        pick_source = "round_default"

    label = f"{season} Round {round_no} (Pick {round_pick})" if season else f"Round {round_no} (Pick {round_pick})"
    if owner_team_name:
        label = f"{label} · {owner_team_name}"

    return {
        "asset_type": "pick",
        "label": label,
        "name": label,
        "score": score,
        "value_score": score,
        "season": season,
        "round": round_no,
        "position": "PICK",
        "owner_roster_id": owner_roster_id,
        "owner_team_name": owner_team_name,
        "original_roster_id": original_roster_id,
        "pick_key": option.get("pick_key"),
        "round_pick": round_pick,
        "pick_source": pick_source,
    }


def drafted_player_asset(
    player_id: Any,
    *,
    df_players,
    score_field: str = "value_score",
) -> dict[str, Any] | None:
    """Build a player asset for an ALREADY-drafted player.

    Uses ``modules.trade_analyzer_assembly.player_asset_from_mapping`` —
    the same adapter the standalone Trade Calculator catalog uses — so an
    already-selected player is valued identically here and there. Never
    loads players itself; ``df_players`` must already be loaded by the
    caller (the live draft page already receives it as a parameter).
    """

    if df_players is None or getattr(df_players, "empty", True):
        return None
    pid = str(player_id or "").strip()
    if not pid or "player_id" not in df_players.columns:
        return None
    matches = df_players[df_players["player_id"].astype(str) == pid]
    if matches.empty:
        return None
    row = matches.iloc[0]
    return player_asset_from_mapping(row, score_field=score_field)


def evaluate_trade(
    *,
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Totals + verdict for a hypothetical live-draft trade.

    Reuses ``score_asset_value``/``trade_value_verdict`` verbatim — the
    same functions and thresholds the standalone Trade Calculator uses.
    Never recomputes or re-bands a value independently.
    """

    send_assets = list(send_assets or [])
    receive_assets = list(receive_assets or [])
    send_total = sum(score_asset_value(asset) for asset in send_assets)
    receive_total = sum(score_asset_value(asset) for asset in receive_assets)
    delta = receive_total - send_total
    return {
        "send_assets": send_assets,
        "receive_assets": receive_assets,
        "send_total": send_total,
        "receive_total": receive_total,
        "delta": delta,
        "verdict": trade_value_verdict(delta),
    }
