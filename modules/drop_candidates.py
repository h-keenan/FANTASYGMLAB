"""Suggested drops: ONE engine for waivers ("Add X, drop Y") and trades that
overfill the roster ("you'd have to drop N").

A drop is a trade with the waiver wire, so it is graded by the same lineup
model as every trade (``modules.roster_value_model.evaluate_swap`` ->
``trade_lineup_model.evaluate_trade``): expected lineup points over the rest
of the season with the league's real slots, byes, injuries and waiver
replacement, plus market value under the team's posture. What this module adds
is the part a points model cannot decide alone, the protections:

never suggested, whatever the arithmetic says
    * players the user marked untouchable (GM Targets);
    * core starters (in the best lineup at least half the remaining weeks);
    * high-value assets (healthy value above a league-scaled threshold);
    * hot / role-growing players (usage trends, display facts used as a guard);
    * young players with real upside, by posture (rebuild protects the most);
    * players whose removal leaves fewer healthy players than starters plus one
      bye/injury cover at the position (superflex / 2QB / TE-premium slots are
      part of the starter count because the model fills them);
    * positions the lineup model does not price (IDP, D/ST).

and the honest outcomes: ``no_good_drop`` when every candidate costs real
value, ``move_to_ir`` (free a spot without dropping anyone) when the league's
IR rules allow it, and ``drop_required: False`` when a roster spot is open.

Pure: frames and mappings in, plain dicts out. Degraded inputs are reported by
``modules.model_status``; nothing is swallowed.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from modules import model_status, roster_value_model as rvm
from modules.frame_records import frame_records

MODEL_VERSION = "drop-candidates-v1"

# A standalone "you could drop" player must cost no more than this many lineup
# points per remaining week and no more than this share of the league's
# high-value threshold (both scale with the league, neither is a fixed number).
DROP_MAX_POINTS_PER_WEEK = 0.35
DROP_MAX_VALUE_SHARE = 0.15
# An "Add X, drop Y" swap must gain more than this share of the high-value
# threshold in posture-weighted score to be recommended.
SWAP_MIN_GAIN_SHARE = 0.01
# Young-upside protection by posture: (max age for skill players, QB age bump,
# minimum healthy value as a share of the high-value threshold).
YOUTH_PROTECTION = {
    "tank": (26.0, 1.0, 0.10),
    "rebuild": (25.0, 2.0, 0.12),
    "retool": (24.0, 2.0, 0.20),
    "fringe_contender": (23.0, 2.0, 0.28),
    "contender": (23.0, 2.0, 0.35),
}
CANDIDATES_PER_ADD = 6
FREE_STANDALONE_LIMIT = 2
MAX_STANDALONE = 8
MAX_ALTERNATIVES = 2


def _ordinal_rank_text(share: float) -> str:
    return f"{share * 100:.0f}%"


def usage_guard(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    """Reduce a ``usage_trends`` profile to what the drop guard needs."""

    if not profile:
        return {"hot": False, "shrinking": False, "label": "", "explanation": ""}
    flags = profile.get("flags") or []
    keys = {f.get("key") for f in flags}
    points = (profile.get("points") or {}).get("direction")
    hot = "role_expanding" in keys or points == "up"
    shrinking = "role_shrinking" in keys or "unsustainable" in keys
    first = flags[0] if flags else {}
    return {
        "hot": bool(hot),
        "shrinking": bool(shrinking and not hot),
        "label": str(first.get("label") or ""),
        "explanation": str(first.get("explanation") or ""),
        "points_direction": points,
    }


def _modeled(position: str) -> bool:
    return position in rvm.MODELED_POSITIONS


def protection_reason(
    rvc: rvm.RosterValueContext,
    player_id: str,
    *,
    untouchable: set[str],
    usage: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str] | None:
    """(code, plain-English reason) when this player must never be suggested."""

    profile = rvc.profiles.get(player_id)
    if profile is None:
        return ("unmodeled", "Not enough data to price him.")
    if player_id in untouchable:
        return ("untouchable", "You marked him untouchable.")
    if not _modeled(profile.position):
        return ("unmodeled", f"{profile.position} players are not part of the lineup model.")
    healthy = rvc.healthy_value.get(player_id, 0.0)
    if rvc.high_value > 0 and healthy >= rvc.high_value:
        return ("high_value", "High-value asset in this league.")
    share = rvc.start_share.get(player_id, 0.0)
    if share >= rvm.CORE_START_SHARE:
        return ("core_starter", "Core starter: in your best lineup most weeks.")
    guard = usage.get(player_id) or {}
    if guard.get("hot"):
        return ("hot_streak", "Trending up: " + (guard.get("explanation") or "recent usage or scoring is rising."))
    max_age, qb_bump, floor_share = YOUTH_PROTECTION.get(rvc.strategy, YOUTH_PROTECTION["retool"])
    age = profile.age
    age_cut = max_age + (qb_bump if profile.position == "QB" else 0.0)
    if age is not None and age <= age_cut and healthy >= floor_share * max(rvc.high_value, 1.0):
        return ("young_upside", "Young with real upside for your team's direction.")
    return None


def _depth_ok(
    rvc: rvm.RosterValueContext, player_id: str, add_positions: Sequence[str], dropped: Sequence[str] = ()
) -> tuple[bool, str]:
    """Would dropping him (and adding ``add_positions``) leave the position with
    its starters plus one bye/injury cover?"""

    profile = rvc.profiles[player_id]
    pos = profile.position
    expected = rvc.expected_starters()
    starters = max(int(round(expected.get(pos, 0.0))), int(rvc.model_ctx.slots.get(pos, 0) or 0))
    required = starters + (1 if pos != "K" else 0)
    healthy = [
        p for p in rvc.active_profiles()
        if p.position == pos and not p.out_all and (p.absence is None or p.absence.weeks < 3)
        and p.player_id not in set(dropped)
    ]
    count = len(healthy) - (1 if profile in healthy else 0) + sum(1 for p in add_positions if p == pos)
    if count < required:
        return False, (
            f"He is one of only {len(healthy)} healthy {pos}s; you need {required} "
            f"({starters} to start plus a bye/injury cover)."
        )
    return True, ""


def _facts(rvc: rvm.RosterValueContext, player_id: str, usage: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    p = rvc.profiles[player_id]
    row = rvc.row(player_id) or {}
    return {
        "player_id": player_id,
        "name": p.name,
        "position": p.position,
        "team": p.team,
        "age": p.age,
        "status": rvm._text(row.get("status")),
        "injury_status": rvm._text(row.get("injury_status")),
        "value": round(rvc.healthy_value.get(player_id, 0.0)),
        "start_share": round(rvc.start_share.get(player_id, 0.0), 2),
        "usage_flag": (usage.get(player_id) or {}).get("label") or None,
    }


def _reasons(
    rvc: rvm.RosterValueContext,
    player_id: str,
    standalone: Mapping[str, Any],
    usage: Mapping[str, Mapping[str, Any]],
    ir_move: bool,
) -> list[str]:
    p = rvc.profiles[player_id]
    pts = standalone["points"]
    reasons: list[str] = []
    if ir_move:
        reasons.append("ruled out and IR-eligible: move him to IR instead of dropping")
    share = rvc.start_share.get(player_id, 0.0)
    costless = pts["ros_delta"] > -0.5
    if share <= 0.0 and costless:
        reasons.append("never starts in your best lineup and losing him costs your lineup nothing")
    else:
        if share <= 0.0:
            reasons.append("never starts in your best lineup")
        elif share < rvm.CORE_START_SHARE:
            reasons.append(f"starts only {share * 100:.0f}% of the remaining weeks (bye and injury fill-in)")
        if costless:
            reasons.append("losing him costs your lineup about nothing")
        else:
            reasons.append(f"losing him costs ~{abs(pts['ros_delta']):.0f} lineup points over the rest of the season")
    fas = rvm.best_free_agents(rvc, p.position, 1)
    if fas and p.ppg is not None and (fas[0].ppg or 0.0) >= (p.ppg or 0.0):
        reasons.append(f"{fas[0].name} on the wire projects as well or better")
    value = rvc.healthy_value.get(player_id, 0.0)
    if rvc.high_value > 0:
        share_of = value / rvc.high_value
        if share_of < 0.15:
            reasons.append("low trade/dynasty value")
    if p.absence is not None and p.absence.weeks >= 6:
        reasons.append(f"out ~{p.absence.weeks:.0f} more weeks")
    guard = usage.get(player_id) or {}
    if guard.get("shrinking") and guard.get("explanation"):
        reasons.append(f"role shrinking: {guard['explanation']}")
    if p.age is not None and rvm._aging(p) and rvc.strategy in ("rebuild", "tank", "retool"):
        reasons.append(f"age {p.age:.0f}, past the point where {p.position}s hold value")
    if ir_move:
        reasons.append("IR-eligible: move him to IR instead of dropping")
    return reasons[:4]


def candidate_pool(
    rvc: rvm.RosterValueContext,
    *,
    untouchable: set[str],
    usage: Mapping[str, Mapping[str, Any]],
    add_positions: Sequence[str] = (),
    exclude: set[str] = frozenset(),
    dropped: Sequence[str] = (),
) -> tuple[list[str], list[dict[str, Any]]]:
    """(droppable player ids, protected players with their reason).

    Only players who occupy an active roster spot can make room for an add."""

    ids: list[str] = []
    protected: list[dict[str, Any]] = []
    for pid in rvc.limits.active_ids:
        if pid in exclude or pid not in rvc.profiles:
            continue
        reason = protection_reason(rvc, pid, untouchable=untouchable, usage=usage)
        if reason is None:
            ok, why = _depth_ok(rvc, pid, add_positions, dropped)
            if not ok:
                reason = ("depth_floor", why)
        if reason is not None:
            protected.append({**_facts(rvc, pid, usage), "protected_by": reason[0], "protected_reason": reason[1]})
        else:
            ids.append(pid)
    return ids, protected


def _score(rvc: rvm.RosterValueContext, drop: str, add_rows: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    return rvm.evaluate_swap(rvc, [drop], add_rows)


def _effect(result: Mapping[str, Any]) -> dict[str, Any]:
    pts = result["points"]
    return {
        "lineup_points_ros": pts["ros_delta"],
        "lineup_points_per_week": pts["per_week_delta"],
        "this_week": pts["this_week_delta"],
        "value_delta": result["raw_value_delta"],
        "score": result["trade_score"],
        "weeks": result["weeks"]["count"],
    }


def passes_free_bar(rvc: rvm.RosterValueContext, player_id: str, standalone: Mapping[str, Any]) -> bool:
    """THE bar for a "free" drop, shared by the standalone list and the per-add
    suggestions: removing him costs at most ``DROP_MAX_POINTS_PER_WEEK`` lineup
    points per week and at most ``DROP_MAX_VALUE_SHARE`` of the league's
    high-value threshold in value (lineup model, real waiver pool as fill-in)."""

    weeks = max(1, rvc.weeks)
    pts = standalone["points"]["ros_delta"]
    value = rvc.healthy_value.get(player_id, 0.0)
    return not (pts / weeks < -DROP_MAX_POINTS_PER_WEEK or value > DROP_MAX_VALUE_SHARE * max(rvc.high_value, 0.0))


def droppable_players(
    rvc: rvm.RosterValueContext,
    *,
    untouchable: set[str],
    usage: Mapping[str, Mapping[str, Any]],
    limit: int = MAX_STANDALONE,
    named: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """"Players you could drop", worst first: ONE list for the whole screen.

    It contains every player who passes the shared free bar
    (``passes_free_bar``) AND every player a suggestion names as the cut for an
    add (``named``: player id -> add names), so a card and this list can never
    disagree. Named players are always listed; ``limit`` caps the rest."""

    named = dict(named or {})
    ids, protected = candidate_pool(rvc, untouchable=untouchable, usage=usage)
    # Named players passed the same protections to be suggested; include them even
    # if the pool changed order (they are in ``ids`` by construction).
    rows: list[dict[str, Any]] = []
    # A named cut that the pool excludes (e.g. an injured high-value player a card
    # moves to IR) is still listed: the list must contain everything a card names.
    extra = [pid for pid in named if pid not in ids and pid in rvc.profiles]
    for pid in [*ids, *extra]:
        result = _score(rvc, pid)
        free = passes_free_bar(rvc, pid, result)
        if not free and pid not in named:
            continue
        ir_move = _ir_move_possible(rvc, pid)
        reasons = _reasons(rvc, pid, result, usage, ir_move)
        if pid in named and not free:
            reasons = [f"cheapest cut to make room for {', '.join(list(named[pid])[:2])}", *reasons][:4]
        rows.append({
            **_facts(rvc, pid, usage),
            "reasons": reasons,
            "effect": _effect(result),
            "action": "move_to_ir" if ir_move else "drop",
            "named_for": list(named.get(pid, [])),
            "_sort": (0 if pid in named else 1, -result["trade_score"], rvc.healthy_value.get(pid, 0.0)),
        })
    rows.sort(key=lambda r: r["_sort"])
    for r in rows:
        r.pop("_sort")
    n_named = sum(1 for r in rows if r["named_for"])
    shown = rows[: max(n_named, max(0, limit))]
    return {
        "players": shown,
        "total": len(rows),
        "locked_count": len(rows) - len(shown),
        "protected_count": len(protected),
        "candidates_checked": len(ids),
    }


def _ir_move_possible(rvc: rvm.RosterValueContext, player_id: str) -> bool:
    if rvc.limits.open_ir_slots <= 0:
        return False
    row = rvc.row(player_id) or {}
    return rvm.ir_eligible(row.get("status"), row.get("injury_status"), rvc.league) and rvm.is_ruled_out(
        row.get("status"), row.get("injury_status")
    )


def _why_swap(add: Mapping[str, Any], drop: Mapping[str, Any], effect: Mapping[str, Any], action: str) -> str:
    verb = "move to IR" if action == "move_to_ir" else "drop"
    parts = [f"Add {add['name']}, {verb} {drop['name']}."]
    if drop.get("reasons"):
        parts.append(f"{drop['name']}: {drop['reasons'][0]}.")
    pts = effect["lineup_points_ros"]
    if abs(pts) >= 0.5:
        parts.append(f"Net {'+' if pts >= 0 else '-'}{abs(pts):.0f} lineup points over the next {effect['weeks']} weeks.")
    else:
        parts.append("No change to your lineup points.")
    value = effect["value_delta"]
    if action == "drop" and abs(value) >= 100:
        parts.append(f"Value {'+' if value >= 0 else '-'}{abs(value):,} ({drop['name']} {drop['value']:,} to {add['name']} {drop['value'] + value:,}).")
    return " ".join(parts).replace("..", ".")


def suggest_drop_for_add(
    rvc: rvm.RosterValueContext,
    add_row: Mapping[str, Any],
    *,
    untouchable: set[str],
    usage: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """"Add X, drop Y" for one waiver target, with up to two alternatives."""

    add_id = str(add_row.get("player_id"))
    add_pos = rvm._text(add_row.get("position")).upper()
    add_name = rvm._text(add_row.get("name")) or add_id
    limits = rvc.limits
    base = {
        "add": {"player_id": add_id, "name": add_name, "position": add_pos},
        "roster": limits.to_public(),
        "drop_required": bool(limits.is_full) if limits.active_limit is not None else None,
    }
    if not _modeled(add_pos):
        return {**base, "status": "unmodeled", "drop": None, "alternatives": [], "no_good_drop": False,
                "why": f"{add_pos or 'This position'} is not part of the lineup model, so no drop is suggested."}
    ids, protected = candidate_pool(rvc, untouchable=untouchable, usage=usage, add_positions=[add_pos])
    scored: list[tuple[float, str, dict[str, Any], bool]] = []
    # Cheap pre-ranking on standalone cost keeps the number of swap evaluations bounded.
    pre = sorted(ids, key=lambda pid: (rvc.healthy_value.get(pid, 0.0), pid))[: CANDIDATES_PER_ADD * 2]
    standalone: dict[str, dict[str, Any]] = {pid: _score(rvc, pid) for pid in pre}
    short = sorted(pre, key=lambda pid: -standalone[pid]["trade_score"])[:CANDIDATES_PER_ADD]
    for pid in short:
        swap = _score(rvc, pid, [add_row])
        ir_move = _ir_move_possible(rvc, pid)
        scored.append((swap["trade_score"], pid, swap, ir_move))
    # IR moves cost nothing in value: the player stays on the roster.
    ir_candidates = [
        pid for pid in limits.active_ids
        if pid in rvc.profiles and pid not in {s[1] for s in scored} and _ir_move_possible(rvc, pid)
    ]
    for pid in ir_candidates:
        swap = rvm.evaluate_swap(rvc, [], [add_row])
        scored.append((float("inf"), pid, swap, True))
    scored.sort(key=lambda s: (-s[0], s[1]))
    threshold = SWAP_MIN_GAIN_SHARE * max(rvc.high_value, 1.0)

    def build(entry: tuple[float, str, dict[str, Any], bool]) -> dict[str, Any]:
        _, pid, swap, ir_move = entry
        stand = standalone.get(pid) or _score(rvc, pid)
        item = {
            **_facts(rvc, pid, usage),
            "reasons": _reasons(rvc, pid, stand, usage, ir_move),
            "effect": _effect(swap),
            "action": "move_to_ir" if ir_move else "drop",
        }
        item["why"] = _why_swap(base["add"], item, item["effect"], item["action"])
        return item

    # A cut is good when it is an IR move, a real upgrade (net gain over the
    # bar), or a free drop by the SAME bar the standalone list uses.
    good = [
        s for s in scored
        if (s[3] and s[0] == float("inf")) or s[0] > threshold
        or (s[1] in standalone and passes_free_bar(rvc, s[1], standalone[s[1]]))
    ]
    result: dict[str, Any] = {**base, "status": "ok", "protected_count": len(protected)}
    if limits.active_limit is not None and not limits.is_full:
        result.update({
            "drop": None, "alternatives": [], "no_good_drop": False, "drop_required": False,
            "why": f"You have {limits.open_spots} open roster spot{'s' if limits.open_spots != 1 else ''}, so you can add {add_name} without dropping anyone.",
        })
        return result
    if good:
        best = build(good[0])
        result.update({
            "drop": best, "alternatives": [build(s) for s in good[1:1 + MAX_ALTERNATIVES]],
            "no_good_drop": False, "why": best["why"],
        })
        return result
    cheapest = build(scored[0]) if scored else None
    why = f"No good drop for {add_name}."
    if cheapest:
        eff = cheapest["effect"]
        costs = eff["value_delta"] < 0 or eff["lineup_points_ros"] <= -0.5
        why += (
            f" Every player you could cut costs real value; the cheapest is {cheapest['name']} "
            if costs
            else f" The best cut, {cheapest['name']}, barely helps "
        ) + f"({eff['lineup_points_ros']:+.0f} lineup pts, value {eff['value_delta']:+,})."
    else:
        why += " Everyone else on your roster is protected (starters, high-value assets, depth you need, or untouchable)."
    result.update({"drop": None, "alternatives": [], "no_good_drop": True, "cheapest": cheapest, "why": why})
    return result


def drops_for_overflow(
    rvc: rvm.RosterValueContext,
    *,
    need: int,
    protect_ids: set[str],
    untouchable: set[str],
    usage: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Choose ``need`` players to cut to make room (a roster-overfilling
    trade), one at a time, each judged on the roster that remains after the
    previous cut. ``rvc`` describes the roster AFTER the trade; ``protect_ids``
    are the players the trade brings in (never the ones to cut)."""

    chosen: list[dict[str, Any]] = []
    dropped: list[str] = []
    prior: dict[str, Any] = {}
    for _ in range(max(0, need)):
        ids, _protected = candidate_pool(
            rvc, untouchable=untouchable, usage=usage, exclude=set(dropped) | set(protect_ids),
            dropped=dropped,
        )
        if not ids:
            break
        best_id, best = None, None
        for pid in sorted(ids, key=lambda p: (rvc.healthy_value.get(p, 0.0), p))[: CANDIDATES_PER_ADD * 2]:
            res = rvm.evaluate_swap(rvc, [*dropped, pid], ())
            if best is None or res["trade_score"] > best["trade_score"]:
                best_id, best = pid, res
        stand = _score(rvc, best_id)
        cumulative = _effect(best)
        # Each cut shows its OWN cost (the step from the previous cumulative
        # effect); the plan's ``effect`` below is the total.
        marginal = {
            key: round(cumulative[key] - prior.get(key, 0), 1) if isinstance(cumulative[key], float) else cumulative[key] - prior.get(key, 0)
            for key in ("lineup_points_ros", "lineup_points_per_week", "this_week", "value_delta", "score")
        }
        marginal["weeks"] = cumulative["weeks"]
        chosen.append({
            **_facts(rvc, best_id, usage),
            "reasons": _reasons(rvc, best_id, stand, usage, False),
            "effect": marginal,
        })
        prior = cumulative
        dropped.append(best_id)
    final = rvm.evaluate_swap(rvc, dropped, ()) if dropped else None
    return {
        "need": need,
        "drops": chosen,
        "dropped_ids": dropped,
        "satisfied": len(chosen) >= need,
        "effect": _effect(final) if final else None,
    }


def build_drop_board(
    rvc: rvm.RosterValueContext,
    adds: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    untouchable: set[str],
    usage: Mapping[str, Mapping[str, Any]],
    standalone_cap: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """The whole drop surface from ONE definition: (suggestion per add id, the
    standalone list). Every cut a suggestion names is in the list; the list is
    empty only when no suggestion names a cut."""

    suggestions = {
        add_id: suggest_drop_for_add(rvc, row, untouchable=untouchable, usage=usage) for add_id, row in adds
    }
    named: dict[str, list[str]] = {}
    for add_id, row in adds:
        cut = suggestions[add_id].get("drop")
        if cut:
            named.setdefault(str(cut["player_id"]), []).append(rvm._text(row.get("name")))
    droppable = droppable_players(
        rvc, untouchable=untouchable, usage=usage, limit=standalone_cap, named=named
    )
    return suggestions, droppable


def plan_trade_overflow(
    *,
    my_team_df: pd.DataFrame,
    all_players_df: pd.DataFrame,
    waiver_df: pd.DataFrame | None,
    my_roster: Mapping[str, Any],
    league: Mapping[str, Any],
    settings: Mapping[str, Any],
    score_field: str,
    strategy: str,
    window: Any,
    league_rostered_values: Sequence[float],
    send_player_ids: Sequence[str],
    receive_player_ids: Sequence[str],
    untouchable_provider: Callable[[], set[str] | None],
    usage_provider: Callable[[rvm.RosterValueContext], Mapping[str, Mapping[str, Any]]],
    status: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Would this trade overfill the roster, and who would have to go?

    ``None`` when the roster limit is unknown or the trade fits. Otherwise the
    drops (same engine as Waivers), their net effect, and ``forced_assets``
    (internal: the fit prices the cuts as part of the trade). Incoming players
    who are IR-eligible use open IR slots first."""

    limits = rvm.roster_limits(league, my_roster)
    if limits.active_limit is None:
        return None
    send = {str(p) for p in send_player_ids}
    mine = {str(p) for p in (my_roster.get("players") or [])}
    incoming_ids = [str(p) for p in receive_player_ids if str(p) not in mine]
    if not incoming_ids and not send:
        return None
    frame = all_players_df[all_players_df["player_id"].astype(str).isin(set(incoming_ids))]
    incoming_rows = frame_records(frame)
    ir_room = limits.open_ir_slots + sum(1 for pid in limits.ir_ids if pid in send)
    ir_placed = []
    for row in incoming_rows:
        if len(ir_placed) < ir_room and rvm.ir_eligible(row.get("status"), row.get("injury_status"), league) and rvm.is_ruled_out(
            row.get("status"), row.get("injury_status")
        ):
            ir_placed.append(str(row["player_id"]))
    sent_active = [pid for pid in limits.active_ids if pid in send]
    active_after = limits.active_count - len(sent_active) + len(incoming_ids) - len(ir_placed)
    need = active_after - limits.active_limit
    if need <= 0:
        return None
    post_ids = [pid for pid in (my_roster.get("players") or []) if str(pid) not in send] + incoming_ids
    post_roster = {
        "players": post_ids,
        "reserve": [p for p in (my_roster.get("reserve") or []) if str(p) not in send] + ir_placed,
        "taxi": [p for p in (my_roster.get("taxi") or []) if str(p) not in send],
    }
    keep = my_team_df[~my_team_df["player_id"].astype(str).isin(send)]
    post_df = pd.concat([keep, frame], ignore_index=True)
    rvc_post = rvm.build_context(
        roster_df=post_df,
        all_players_df=all_players_df,
        pool=waiver_df,
        my_roster=post_roster,
        league=league,
        settings=settings,
        score_field=score_field,
        strategy=strategy,
        window=window,
        league_rostered_values=league_rostered_values,
        status=status,
    )
    # The untouchable list is read only now that a cut is actually needed. When
    # it cannot be read no player is named (it could be one the user protected):
    # the plan says so and the caller reports the marker.
    untouchable = untouchable_provider()
    if untouchable is None:
        return {
            "need": need, "drops": [], "dropped_ids": [], "satisfied": False, "effect": None,
            "unavailable": "untouchable_lookup_failed", "roster": limits.to_public(),
            "incoming_to_ir": ir_placed, "active_after": active_after, "active_limit": limits.active_limit,
            "forced_assets": [],
        }
    plan = drops_for_overflow(
        rvc_post, need=need, protect_ids=set(incoming_ids), untouchable=untouchable,
        usage=usage_provider(rvc_post),
    )
    from modules.trade_analyzer_assembly import player_asset_from_mapping

    rows = {str(r["player_id"]): r for r in frame_records(post_df)}
    forced = [
        {**player_asset_from_mapping(rows[pid], score_field=score_field), "forced_drop": True}
        for pid in plan["dropped_ids"] if pid in rows
    ]
    return {
        **plan,
        "roster": limits.to_public(),
        "incoming_to_ir": ir_placed,
        "active_after": active_after,
        "active_limit": limits.active_limit,
        "forced_assets": forced,
    }


def public_overflow(plan: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The overflow plan without internal assets, for payloads."""

    if not plan:
        return None
    return {k: v for k, v in plan.items() if k not in {"forced_assets", "dropped_ids"}}
