"""Season grade and "decisions that mattered".

Decisions are measured by counterfactual replay: because every random draw is
keyed by (week, subsystem, team), re-running the season with one user decision
removed shares all unaffected randomness with the base run, so the difference in
outcome is attributable to that decision rather than to dice.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from modules.sim.engine import SeasonOutcome, simulate_season
from modules.sim.types import LeagueSnapshot, Strategy

MAX_DECISIONS = 4
CURVE_BASE = 45.0
CURVE_SLOPE = 0.62
MAX_INDIVIDUAL_REPLAYS = 7
PLAYOFF_VALUE = {
    "missed": 0.0, "lost_round_1": 0.5, "lost_round_2": 1.5, "lost_round_3": 2.5,
    "semifinal": 2.0, "runner_up": 3.0, "champion": 4.5,
}
PLAYOFF_LABEL = {
    "missed": "missed the playoffs", "lost_round_1": "lost in the first round",
    "lost_round_2": "lost in the second round", "lost_round_3": "lost in the third round",
    "semifinal": "lost in the semifinals", "runner_up": "lost in the final", "champion": "won the title",
}
LETTERS = [
    (93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (77, "C+"),
    (73, "C"), (70, "C-"), (67, "D+"), (63, "D"), (60, "D-"),
]


def outcome_value(outcome: SeasonOutcome) -> float:
    """One number for "how good was the user's season": wins plus playoff depth."""

    user = outcome.user
    return user["wins"] + 0.5 * user["ties"] + PLAYOFF_VALUE.get(user["playoff_result"], 0.0)


def letter_for(score: float) -> str:
    for floor, letter in LETTERS:
        if score >= floor:
            return letter
    return "F"


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _impact(base: SeasonOutcome, alt: SeasonOutcome) -> dict[str, Any]:
    games = max(1, base.user["games"])
    return {
        "season_value": round(outcome_value(base) - outcome_value(alt), 2),
        "wins": round(base.user["wins"] - alt.user["wins"], 1),
        "points_per_game": round((base.user["pf"] - alt.user["pf"]) / games, 2),
        "playoff_result_with": base.user["playoff_result"],
        "playoff_result_without": alt.user["playoff_result"],
    }


def _verb(impact: dict[str, Any]) -> str:
    value = impact["season_value"]
    if value >= 0.25:
        return "helped"
    if value <= -0.25:
        return "hurt"
    return "barely moved the needle on"


def _names(assets: list[dict[str, Any]]) -> str:
    return ", ".join(a["name"] for a in assets) or "nothing"


def _evaluate_decisions(
    snapshot: LeagueSnapshot, strategy: Strategy, seed: int, base: SeasonOutcome
) -> list[dict[str, Any]]:
    user_events = [e for e in base.events if e.get("involves_user") and e["type"] in ("trade", "waiver")]
    decisions: list[dict[str, Any]] = []

    def user_gives(event: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if event["team"] == snapshot.user_team.tid:
            return event["gives"], event["gets"]
        return event["gets"], event["gives"]

    trades = [e for e in user_events if e["type"] == "trade"]
    waivers = sorted(
        (e for e in user_events if e["type"] == "waiver"), key=lambda e: (-e["gain"], e["seq"])
    )
    individual = (trades + waivers)[:MAX_INDIVIDUAL_REPLAYS]
    for event in individual:
        alt = simulate_season(snapshot, strategy, seed, veto=[event["key"]])
        impact = _impact(base, alt)
        if event["type"] == "trade":
            sent, got = user_gives(event)
            title = f"Week {event['week']} trade: sent {_names(sent)}, got {_names(got)}"
            detail = f"That deal {_verb(impact)} your season ({_impact_text(impact)})."
            if any(asset.get("kind") == "pick" for asset in sent + got):
                detail += " Draft picks have no on-field value this season, so their future worth is not scored."
            kind = "trade"
        else:
            drop = f", dropped {event['drop']['name']}" if event["drop"] else ""
            title = f"Week {event['week']} waiver: added {event['add']['name']}{drop}"
            detail = f"That pickup {_verb(impact)} your season ({_impact_text(impact)})."
            kind = "waiver"
        decisions.append({"kind": kind, "week": event["week"], "title": title, "detail": detail, "impact": impact})

    # Strategy-level decisions, each against its opposite.
    no_trades = simulate_season(snapshot, replace(strategy, trade_aggressiveness=0.0), seed)
    impact = _impact(base, no_trades)
    made = len(trades)
    decisions.append({
        "kind": "strategy_trades", "week": None,
        "title": f"Trade strategy ({strategy.posture.replace('_', ' ')}, aggressiveness {strategy.trade_aggressiveness:.1f})",
        "detail": (
            f"Your auto-GM made {made} trade{'s' if made != 1 else ''}; against never trading, "
            f"that {_verb(impact)} your season ({_impact_text(impact)})."
        ),
        "impact": impact,
    })
    no_waivers = simulate_season(snapshot, replace(strategy, waiver_aggressiveness=0.0), seed)
    impact = _impact(base, no_waivers)
    adds = len([e for e in user_events if e["type"] == "waiver"])
    decisions.append({
        "kind": "strategy_waivers", "week": None,
        "title": f"Waiver strategy (aggressiveness {strategy.waiver_aggressiveness:.1f})",
        "detail": (
            f"{adds} pickup{'s' if adds != 1 else ''}; against ignoring the wire, "
            f"that {_verb(impact)} your season ({_impact_text(impact)})."
        ),
        "impact": impact,
    })
    flipped = simulate_season(snapshot, replace(strategy, lineup_auto_set=not strategy.lineup_auto_set), seed)
    impact = _impact(base, flipped)
    decisions.append({
        "kind": "strategy_lineup", "week": None,
        "title": "Lineup auto-set " + ("on" if strategy.lineup_auto_set else "off"),
        "detail": (
            f"{'Auto-setting' if strategy.lineup_auto_set else 'Setting it and forgetting it'} "
            f"{_verb(impact)} your season against the alternative ({_impact_text(impact)})."
        ),
        "impact": impact,
    })
    decisions.sort(key=lambda d: (-abs(d["impact"]["season_value"]), d["kind"], d.get("week") or 0, d["title"]))
    return decisions


def _impact_text(impact: dict[str, Any]) -> str:
    wins = impact["wins"]
    sign = "+" if wins > 0 else ""
    return (
        f"{sign}{wins:g} wins, {impact['points_per_game']:+.1f} points per game, "
        f"{PLAYOFF_LABEL.get(impact['playoff_result_with'], impact['playoff_result_with'])} vs "
        f"{PLAYOFF_LABEL.get(impact['playoff_result_without'], impact['playoff_result_without'])} without it"
    )


def grade_season(
    snapshot: LeagueSnapshot, base: SeasonOutcome, decisions: list[dict[str, Any]]
) -> dict[str, Any]:
    n = len(base.standings)
    user = base.user
    rank = next(i for i, row in enumerate(base.standings) if row["is_user"]) + 1
    record_score = 100.0 * (n - rank) / max(1, n - 1)
    pf_sorted = sorted((row["pf"] for row in base.standings), reverse=True)
    pf_rank = pf_sorted.index(user["pf"]) + 1
    points_score = 100.0 * (n - pf_rank) / max(1, n - 1)
    playoff_score = {
        "champion": 100.0, "runner_up": 82.0, "semifinal": 68.0, "lost_round_3": 60.0,
        "lost_round_2": 55.0, "lost_round_1": 48.0, "missed": 0.0,
    }.get(user["playoff_result"], 45.0)
    efficiency_score = _clip((user["lineup_efficiency"] - 0.8) / 0.2 * 100.0)
    # Transactions: net season value of the user's individual trades/waivers.
    net = sum(
        d["impact"]["season_value"] for d in decisions if d["kind"] in ("trade", "waiver")
    )
    transaction_score = _clip(50.0 + 25.0 * net)
    components = [
        ("record", "Record and seeding", record_score, 0.35),
        ("points", "Points scored", points_score, 0.20),
        ("playoffs", "Playoff result", playoff_score, 0.25),
        ("lineup", "Lineup efficiency", efficiency_score, 0.10),
        ("transactions", "Trades and waivers", transaction_score, 0.10),
    ]
    score = sum(value * weight for _, _, value, weight in components)
    # Graded on a curve: a typical manager (middle of the pack, no playoff
    # run) lands around a C; a title run with clean management lands in A range.
    curved = min(100.0, CURVE_BASE + CURVE_SLOPE * score)
    return {
        "score": round(score, 1),
        "grade_points": round(curved, 1),
        "letter": letter_for(curved),
        "components": [
            {"key": key, "label": label, "score": round(value, 1), "weight": weight}
            for key, label, value, weight in components
        ],
        "summary": {
            "record": f"{user['wins']:g}-{user['losses']:g}" + (f"-{user['ties']:g}" if user["ties"] else ""),
            "finish": rank,
            "points_rank": pf_rank,
            "playoff_result": user["playoff_result"],
            "lineup_efficiency": user["lineup_efficiency"],
            "luck_wins": round(user["wins"] + 0.5 * user["ties"] - user["expected_wins"], 2),
        },
    }


def run_world(snapshot: LeagueSnapshot, strategy: Strategy, seed: int, *, explain: bool = True) -> dict[str, Any]:
    """Simulate the season and, if ``explain``, grade it and attribute the
    decisions that mattered. Returns the full JSON-able result."""

    base = simulate_season(snapshot, strategy, seed)
    result = base.to_dict()
    result["strategy"] = strategy.to_dict()
    if not explain:
        return result
    decisions = _evaluate_decisions(snapshot, strategy, seed, base)
    result["grade"] = grade_season(snapshot, base, decisions)
    result["decisions_that_mattered"] = decisions[:MAX_DECISIONS]
    return result
