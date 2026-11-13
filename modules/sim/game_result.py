"""Replay, the season grade and "decisions that mattered" for the GM game.

``replay_game`` re-runs a whole game from its frozen snapshot, seed and the
user's own commands (every event with ``actor == "user"``), regenerating all AI
behavior, scoring and injuries. With nothing vetoed it reproduces the original
state exactly (the determinism test). With one user decision skipped it is a
counterfactual: every random draw is keyed by (seed, week, stream, player/team),
so the alternate season shares all unaffected dice with the real one and the
difference is attributable to that decision.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from modules.sim import game_actions as act
from modules.sim.analysis import CURVE_BASE, CURVE_SLOPE, PLAYOFF_LABEL, PLAYOFF_VALUE, letter_for
from modules.sim.game_ai import TradeDesk
from modules.sim.game_draft import DraftContext, draft_recap, run_ai_picks, set_queue, user_pick
from modules.sim.game_engine import _brief, advance, finish_draft, standing_rows, start_from_league
from modules.sim.game_eval import Evaluator
from modules.sim.game_review import build_review
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GAME_ENGINE_VERSION, GameError, GameSnapshot

MAX_REPLAYS = 6
MAX_DECISIONS = 4


# -------------------------------------------------------------------- replay


def replay_game(
    snap: GameSnapshot, seed: int, events: Sequence[Mapping[str, Any]], *, veto: Iterable[int] = (),
    strict: bool = False,
) -> GameState:
    """Re-run the game from the user's commands. ``veto`` is a set of original
    event seqs (of user commands) to skip. ``strict=True`` raises on any command
    that fails (used when replaying an unmodified log)."""

    skip = set(veto)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    if snap.start_rosters:
        start_from_league(em, snap, state, seed)
    else:
        run_ai_picks(ctx, em, seed)
    claim_map: dict[str, str] = {}
    offer_by_orig: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {}
    for ev in events:
        if ev["type"] == "inbox_offer":
            p = ev["payload"]
            offer_by_orig[p["id"]] = (p["team"], tuple(p["give"]), tuple(p["get"]))
    user = snap.user_team.tid

    def find_offer(sig: tuple[str, tuple[str, ...], tuple[str, ...]]) -> str | None:
        for o in state.offers:
            if (o["team"], tuple(o["give"]), tuple(o["get"])) == sig:
                return o["id"]
        return None

    for ev in events:
        if ev["actor"] != "user" or int(ev["seq"]) in skip:
            continue
        kind, p = ev["type"], ev["payload"]
        try:
            if kind == "draft_queue":
                set_queue(ctx, em, p["pids"])
            elif kind == "draft_pick":
                user_pick(ctx, em, p["pid"], seed, auto=bool(p.get("auto")))
                if state.pick_index >= ctx.total and state.status == "drafting":
                    finish_draft(em, snap, state, seed)
            elif kind == "lineup_set":
                act.auto_lineup(em) if p.get("auto") else act.set_lineup(em, p["slots"])
            elif kind == "waiver_claim":
                claim = act.queue_claim(em, p["add"], p.get("drop"), p.get("start_slot"))
                claim_map[p["id"]] = claim["id"]
            elif kind == "waiver_cancel":
                if p["id"] in claim_map:
                    act.cancel_claim(em, claim_map[p["id"]])
            elif kind == "cut":
                act.cut_player(em, p["pid"])
            elif kind == "trade":
                if p.get("source") == "ai_offer":
                    other = p["team_a"] if p["team_b"] == user else p["team_b"]
                    oid = find_offer((other, tuple(p["give"]), tuple(p["get"])))
                    if oid is not None:
                        act.respond_offer(em, TradeDesk(Evaluator(snap, state), seed), oid, "accept")
                else:
                    act.send_trade(em, TradeDesk(Evaluator(snap, state), seed), p["team_b"], p["give"], p["get"])
            elif kind in ("trade_reject", "trade_counter"):
                act.send_trade(em, TradeDesk(Evaluator(snap, state), seed), p["team"], p["give"], p["get"])
            elif kind == "inbox_response":
                sig = offer_by_orig.get(p["id"])
                oid = find_offer(sig) if sig else None
                if oid is not None:
                    act.respond_offer(em, TradeDesk(Evaluator(snap, state), seed), oid, p["action"])
            elif kind == "advance":
                advance(em, snap, state, seed)
        except (GameError, ValueError):
            if strict:
                raise
    return state


# ------------------------------------------------------------------- summary


def season_summary(snap: GameSnapshot, state: GameState) -> dict[str, Any]:
    user = snap.user_team.tid
    rows = standing_rows(snap, state)
    me = next(r for r in rows if r["team_id"] == user)
    label = (state.playoff or {}).get("results", {}).get(user, "missed")
    return {
        "wins": me["wins"], "losses": me["losses"], "ties": me["ties"], "pf": me["pf"], "pa": me["pa"],
        "rank": me["rank"], "seed": me["seed"], "playoff_result": label,
        "made_playoffs": bool(state.playoff and user in state.playoff["seeds"]),
    }


def outcome_value(summary: Mapping[str, Any]) -> float:
    return summary["wins"] + 0.5 * summary["ties"] + PLAYOFF_VALUE.get(summary["playoff_result"], 0.0)


def _expected_wins(snap: GameSnapshot, state: GameState) -> float:
    user = snap.user_team.tid
    total = 0.0
    for week in state.history:
        if week["kind"] != "regular":
            continue
        scores: dict[str, float] = {}
        for g in week["games"]:
            scores[g["home"]], scores[g["away"]] = g["home_pts"], g["away_pts"]
        others = [v for t, v in scores.items() if t != user]
        if user in scores and others:
            total += sum(1 for v in others if scores[user] > v) / len(others)
    return total


def _efficiency(state: GameState) -> tuple[float, list[dict[str, Any]]]:
    started = optimal = 0.0
    worst: list[dict[str, Any]] = []
    for key in sorted(state.recaps, key=int):
        g = state.recaps[key].get("your_game")
        if not g or "optimal_pts" not in g:
            continue
        started += g["your_pts"]
        optimal += g["optimal_pts"]
        left = round(g["optimal_pts"] - g["your_pts"], 1)
        worst.append({"week": int(key), "left": left})
    worst.sort(key=lambda w: (-w["left"], w["week"]))
    return (started / optimal if optimal > 0 else 1.0), worst


# ----------------------------------------------------------------- decisions


def _decision_candidates(snap: GameSnapshot, state: GameState, events: Sequence[Mapping[str, Any]]):
    user = snap.user_team.tid
    claims: dict[str, Mapping[str, Any]] = {}
    for e in events:
        if e["type"] == "waiver_claim" and e["actor"] == "user":
            claims[e["payload"]["id"]] = e
    trades, waivers = [], []
    for e in events:
        p = e["payload"]
        if e["type"] == "trade" and e["actor"] == "user" and user in (p["team_a"], p["team_b"]):
            trades.append(e)
        elif e["type"] == "waiver_result" and p["team"] == user and p["ok"] and p.get("claim_id") in claims:
            waivers.append((claims[p["claim_id"]], e))
    return trades, waivers


def _impact(base: Mapping[str, Any], alt: Mapping[str, Any], games: int) -> dict[str, Any]:
    games = max(1, games)
    return {
        "season_value": round(outcome_value(base) - outcome_value(alt), 2),
        "wins": round(base["wins"] - alt["wins"], 1),
        "points_per_game": round((base["pf"] - alt["pf"]) / games, 2),
        "playoff_result_with": base["playoff_result"],
        "playoff_result_without": alt["playoff_result"],
    }


def _verb(value: float) -> str:
    return "helped" if value >= 0.25 else "hurt" if value <= -0.25 else "barely moved the needle on"


def _impact_text(impact: Mapping[str, Any]) -> str:
    wins = impact["wins"]
    sign = "+" if wins > 0 else ""
    return (
        f"{sign}{wins:g} wins, {impact['points_per_game']:+.1f} points per game, "
        f"{PLAYOFF_LABEL.get(impact['playoff_result_with'], impact['playoff_result_with'])} vs "
        f"{PLAYOFF_LABEL.get(impact['playoff_result_without'], impact['playoff_result_without'])} without it"
    )


def evaluate_decisions(
    snap: GameSnapshot, seed: int, events: Sequence[Mapping[str, Any]], final: GameState
) -> list[dict[str, Any]]:
    user = snap.user_team.tid
    base = season_summary(snap, final)
    games = int(base["wins"] + base["losses"] + base["ties"]) or 1
    trades, waivers = _decision_candidates(snap, final, events)
    chosen: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = [("trade", t, t) for t in trades]

    def produced(add_event: tuple[Mapping[str, Any], Mapping[str, Any]]) -> float:
        claim_event, result_event = add_event
        pid = result_event["payload"]["add"]
        return sum(p for p in (final.points.get(pid) or [])[int(result_event["week"]) - 1:] if p is not None)

    waivers.sort(key=lambda w: (-produced(w), int(w[0]["seq"])))
    chosen += [("waiver", c, r) for c, r in waivers]
    decisions: list[dict[str, Any]] = []
    for kind, cmd, res in chosen[:MAX_REPLAYS]:
        alt = season_summary(snap, replay_game(snap, seed, events, veto=[int(cmd["seq"])]))
        impact = _impact(base, alt, games)
        week = int(res["week"])
        if kind == "trade":
            p = cmd["payload"]
            sent, got = (p["give"], p["get"]) if p["team_a"] == user else (p["get"], p["give"])
            names = lambda ids: ", ".join(snap.players[i].name for i in ids) or "nothing"
            title = f"Week {week} trade: sent {names(sent)}, got {names(got)}"
            detail = f"That deal {_verb(impact['season_value'])} your season ({_impact_text(impact)})."
        else:
            p = res["payload"]
            drop = f", dropped {snap.players[p['drop']].name}" if p.get("drop") else ""
            title = f"Week {week} waiver: added {snap.players[p['add']].name}{drop}"
            detail = f"That pickup {_verb(impact['season_value'])} your season ({_impact_text(impact)})."
        if kind == "trade":
            players = [{**_brief(snap, i), "role": "get"} for i in got] + [{**_brief(snap, i), "role": "give"} for i in sent]
        else:
            players = [{**_brief(snap, p["add"]), "role": "add"}] + (
                [{**_brief(snap, p["drop"]), "role": "drop"}] if p.get("drop") else [])
        decisions.append({"kind": kind, "week": week, "title": title, "detail": detail, "impact": impact,
                          "players": players})
    return decisions


def _lineup_decisions(worst: list[dict[str, Any]], final: GameState, snap: GameSnapshot) -> list[dict[str, Any]]:
    out = []
    for w in worst[:2]:
        if w["left"] < 8.0:
            continue
        g = final.recaps[str(w["week"])]["your_game"]
        bench = [b for b in g["bench"] if b["player"]][:1]
        started = [r for r in g["starters"] if r["player"] and r["flag"] is None]
        low = min(started, key=lambda r: r["pts"], default=None)
        extra = ""
        if bench and low:
            extra = f" ({bench[0]['player']['name']} scored {bench[0]['pts']} on your bench while {low['player']['name']} scored {low['pts']} in your lineup)"
        players = ([{**_brief(snap, bench[0]["player"]["id"]), "role": "bench", "pts": bench[0]["pts"]}] if bench else []) + (
            [{**_brief(snap, low["player"]["id"]), "role": "started", "pts": low["pts"]}] if low else [])
        out.append({
            "kind": "lineup", "week": w["week"], "players": players,
            "title": f"Week {w['week']}: {w['left']} points sat on your bench",
            "detail": f"In hindsight a different lineup was worth {w['left']} more points that week{extra}.",
            "impact": {"season_value": round(-min(1.0, w["left"] / 60.0), 2), "wins": 0.0,
                       "points_per_game": 0.0, "playoff_result_with": None, "playoff_result_without": None},
        })
    return out


# --------------------------------------------------------------------- grade


def grade_game(
    snap: GameSnapshot, final: GameState, decisions: list[dict[str, Any]], draft: Mapping[str, Any]
) -> dict[str, Any]:
    n = len(snap.tids)
    user = snap.user_team.tid
    summary = season_summary(snap, final)
    rows = standing_rows(snap, final)
    pf_sorted = sorted((r["pf"] for r in rows), reverse=True)
    pf_rank = pf_sorted.index(summary["pf"]) + 1
    efficiency, _ = _efficiency(final)
    expected = _expected_wins(snap, final)
    record = 100.0 * (n - summary["rank"]) / max(1, n - 1)
    points = 100.0 * (n - pf_rank) / max(1, n - 1)
    playoff = {
        "champion": 100.0, "runner_up": 82.0, "semifinal": 68.0, "lost_round_3": 60.0,
        "lost_round_2": 55.0, "lost_round_1": 48.0, "missed": 0.0,
    }.get(summary["playoff_result"], 45.0)
    eff_score = max(0.0, min(100.0, (efficiency - 0.8) / 0.2 * 100.0))
    net = sum(d["impact"]["season_value"] for d in decisions if d["kind"] in ("trade", "waiver"))
    moves = max(0.0, min(100.0, 50.0 + 25.0 * net))
    draft_rank = draft["your_team"]["rank"]
    draft_score = 100.0 * (n - draft_rank) / max(1, n - 1)
    components = [
        ("record", "Record and seeding", record, 0.35),
        ("points", "Points scored", points, 0.20),
        ("playoffs", "Playoff result", playoff, 0.25),
        ("lineup", "Lineup efficiency", eff_score, 0.10),
        ("moves", "Draft and roster moves", 0.5 * draft_score + 0.5 * moves, 0.10),
    ]
    score = sum(v * w for _, _, v, w in components)
    curved = min(100.0, CURVE_BASE + CURVE_SLOPE * score)
    return {
        "score": round(score, 1), "grade_points": round(curved, 1), "letter": letter_for(curved),
        "components": [
            {"key": k, "label": label, "score": round(v, 1), "weight": w} for k, label, v, w in components
        ],
        "summary": {
            "record": f"{summary['wins']}-{summary['losses']}" + (f"-{summary['ties']}" if summary["ties"] else ""),
            "finish": summary["rank"], "points_rank": pf_rank, "playoff_result": summary["playoff_result"],
            "lineup_efficiency": round(efficiency, 4),
            "luck_wins": round(summary["wins"] + 0.5 * summary["ties"] - expected, 2),
            "draft_grade": draft["your_team"]["grade"],
        },
    }


def build_result(
    snap: GameSnapshot, seed: int, events: Sequence[Mapping[str, Any]], final: GameState, *, explain: bool = True
) -> dict[str, Any]:
    """The stored end-of-season result. ``explain`` runs the counterfactual
    replays (about one season-sim each)."""

    draft = next((e["payload"]["recap"] for e in events if e["type"] in ("draft_complete", "league_start")), None)
    if draft is None:
        draft = _draft_from_state(snap, final)
    efficiency, worst = _efficiency(final)
    decisions = evaluate_decisions(snap, seed, events, final) if explain else []
    decisions += _lineup_decisions(worst, final, snap)
    decisions.sort(key=lambda d: (-abs(d["impact"]["season_value"]), d["kind"], d.get("week") or 0, d["title"]))
    grade = grade_game(snap, final, decisions, draft)
    rows = standing_rows(snap, final)
    for r in rows:
        r["playoff_result"] = (final.playoff or {}).get("results", {}).get(r["team_id"], "missed")
    user = snap.user_team.tid
    weeks = []
    for key in sorted(final.recaps, key=int):
        g = final.recaps[key].get("your_game")
        if g and "your_pts" in g:
            weeks.append({"week": int(key), "opponent": g["opponent_name"], "you": g["your_pts"],
                          "them": g["opp_pts"], "result": g["result"]})
    return {
        "engine_version": GAME_ENGINE_VERSION, "seed": seed,
        "champion": {"team_id": final.champion, "name": snap.team(final.champion).name} if final.champion else None,
        "final_standings": rows, "user": {**season_summary(snap, final), "team_id": user,
                                          "lineup_efficiency": round(efficiency, 4),
                                          "expected_wins": round(_expected_wins(snap, final), 2)},
        "grade": grade, "decisions_that_mattered": decisions[:MAX_DECISIONS],
        "draft": {"grade": draft["your_team"]["grade"], "rank": draft["your_team"]["rank"],
                  "best_pick": draft["your_team"]["best_pick"], "worst_pick": draft["your_team"]["worst_pick"]},
        "weeks": weeks,
        "review": build_review(snap, events, final, draft),
    }


def _draft_from_state(snap: GameSnapshot, final: GameState) -> dict[str, Any]:
    return draft_recap(snap, final)


__all__ = [
    "replay_game", "season_summary", "outcome_value", "evaluate_decisions", "grade_game", "build_result",
]
