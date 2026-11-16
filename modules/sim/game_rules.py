"""The Realism update: switching newer rules on in a game that was made before them.

A game's settings are frozen when it is created, and every rule generation (``hint_v``, ``world_v``, ``aging_v`` ...) is a
gate in them, so a save from before a gate keeps the old behaviour for good (that is what keeps old logs replaying
byte-identically). The Realism update is the one sanctioned way to move such a save forward, and it is **event-sourced**:
the user's command appends one ``realism_upgrade`` event to the game's log, and the fold records it in ``state.rules``
(the game's settings history). Everything that reads a setting afterwards is handed the settings *in force at that point of
the log*, so:

* a log without the event never has a rule entry and replays exactly as it always did (the digest leaves ``rules`` out
  while it is empty);
* a log with the event replays deterministically: the entry is a pure function of the event payload, and a replay applies the
  flag from the event's position, not before;
* undo / revert-week past the event deletes it, and the flags revert with it.

Each upgradable flag declares WHEN it takes effect (``UPGRADABLE_FLAGS[name] = (target_value, boundary)``):

``"now"``
    Decisions made after the event (trade verdicts, the draft hint, roster-limit checks). Nothing already recorded changes.
``"week"``
    The next simulated week and everything after it. A game's pending decisions always sit at a week boundary (the week
    in progress has not been simulated), so this is the same instant as ``"now"`` for the weekly engine; it also reaches the
    dynasty pool generation like ``"season"`` does (a season's pool is built once, when the offseason starts).
``"season"``
    The next offseason / season boundary: the first dynasty season *generated* after the event (retirements, aging, the
    rookie class). Seasons already built are history and stay exactly as they were.

The boundary a flag had when the event was written is stored in the event itself, so changing this registry later never
re-times an old upgrade.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Iterable, Mapping, Sequence

from modules.sim.game_names import NAMES_VERSION
from modules.sim.game_types import (
    AGING_VERSION,
    ECON_VERSION,
    STABILITY_VERSION,
    VORP_VERSION,
    ADVICE_VERSION,
    INCUMBENT_VERSION,
    DEFENSE_VERSION,
    POS_VERSION,
    HINT_VERSION,
    KD_VERSION,
    LIMIT_VERSION,
    WORLD_VERSION,
    GameSettings,
)

NOW, WEEK, SEASON = "now", "week", "season"
BOUNDARIES = (NOW, WEEK, SEASON)

# {flag: (value it is switched to, boundary)}. Add a gate here and the update offers it (see ``FLAGS`` for its copy).
UPGRADABLE_FLAGS: dict[str, tuple[int, str]] = {
    "hint_v": (HINT_VERSION, NOW),
    "limit_v": (LIMIT_VERSION, NOW),
    "kd_v": (KD_VERSION, NOW),
    "world_v": (WORLD_VERSION, WEEK),
    "aging_v": (AGING_VERSION, SEASON),
    "names_v": (NAMES_VERSION, SEASON),
    "econ_v": (ECON_VERSION, NOW),
    "stability_v": (STABILITY_VERSION, SEASON),
    "vorp_v": (VORP_VERSION, NOW),
    "advice_v": (ADVICE_VERSION, NOW),
    "incumbent_v": (INCUMBENT_VERSION, SEASON),
    "defense_v": (DEFENSE_VERSION, WEEK),
    "pos_v": (POS_VERSION, NOW),
}

# What the UI shows for each flag: a short label, one sentence of what changes, and whether it needs a dynasty with offseasons.
FLAGS: dict[str, dict[str, Any]] = {
    "hint_v": {
        "label": "Honest draft help",
        "body": "Draft hints, auto-pick and counter-offers use public information only (ADP, need, projections), never the hidden value.",
        "dynasty_only": False,
    },
    "limit_v": {
        "label": "Roster limit that does not block",
        "body": "Being over the roster limit no longer stops you from advancing; it only blocks adding players until you are back under.",
        "dynasty_only": False,
    },
    "kd_v": {
        "label": "Kickers and defenses can be traded",
        "body": "Kickers and team defenses can be part of trades.",
        "dynasty_only": False,
    },
    "world_v": {
        "label": "Realistic NFL usage",
        "body": "A backup QB sits unless the starter is out, a team's backs, receivers and tight ends cannot all out-score their usual share, and new dynasty depth charts and rookie landing spots follow the players.",
        "dynasty_only": False,
    },
    "aging_v": {
        "label": "Realistic aging and retirement",
        "body": "Retirement follows position, age, role and production (a 33-year-old starting QB is not retired by default), and aging curves are flatter for QBs and kickers.",
        "dynasty_only": True,
    },
    "econ_v": {
        "label": "Fair trades",
        "body": "AI managers stop selling stars below market value: draft picks are priced like the rookies they become, injuries cost the share of the season missed, and a player no better than the waiver wire is worth nothing in a trade.",
        "dynasty_only": False,
    },
    "stability_v": {
        "label": "A league that stays balanced",
        "body": "A good or bad season now carries into a player's next projection, young backs, receivers and tight ends keep improving through their early years, rookie classes refill the depth that retirements take, and AI managers trade players (not picks) with each other at market value so talent stops piling up on a few teams. New rookie classes also vary more in year one.",
        "dynasty_only": False,
    },
    "vorp_v": {
        "label": "Fair prices for backup quarterbacks",
        "body": "Trades value a player by what he adds over a typical starter at his position, so a backup QB in a one-QB league is cheap, and a counter-offer asks for the smallest fair add instead of your best player.",
        "dynasty_only": False,
    },
    "incumbent_v": {
        "label": "Starters keep their jobs",
        "body": "A starting QB, RB, WR or TE keeps his job each offseason unless a challenger is clearly better (a strong season protects him strongly, a bust weakly; age and a high draft pick can change that), and every depth chart change is written to the story log.",
        "dynasty_only": True,
    },
    "defense_v": {
        "label": "Matchups matter",
        "body": "Every NFL defense is stronger or weaker against the QB, RB, WR and TE, changes from season to season, and nudges a player's weekly points and projection by about 5 to 8 percent depending on who he plays.",
        "dynasty_only": False,
    },
    "advice_v": {
        "label": "Smarter draft advice",
        "body": "The draft hint and Auto-pick weigh value against your starting-slot needs, positional runs and thin tiers, byes and injuries, and say why (for example, why a big value gap beats a need).",
        "dynasty_only": False,
    },
    "pos_v": {
        "label": "Kickers and defenses trade like any position",
        "body": "A team that needs a kicker (or defense) will take a better one for fair value and cut its worse one, a team that is set declines a worse one on value, and the Needs tags match what the AI will pay for. Kickers and defenses can go on your trade block.",
        "dynasty_only": False,
    },
    "names_v": {
        "label": "Fresh rookie names",
        "body": "Future rookie classes get names that never repeat inside your save.",
        "dynasty_only": True,
    },
}

BOUNDARY_COPY = {
    NOW: "Right away",
    WEEK: "From the next simulated week",
    SEASON: "From the next offseason",
}

NOT_RETROACTIVE = "Past results stay as they were; new rules apply going forward."


# ------------------------------------------------------------------ pure helpers


def applies(flag: str, settings: GameSettings) -> bool:
    """Whether ``flag`` does anything in a game with ``settings`` (the dynasty rules need a dynasty with offseasons)."""

    info = FLAGS.get(flag)
    if info is None:
        return True
    return bool(settings.multi_season) if info.get("dynasty_only") else True


def rules_key(rules: Sequence[Mapping[str, Any]]) -> tuple:
    """A hashable identity of a rules history (the memo key for the snapshot that applies it)."""

    return tuple(
        (int(e["view_from"]), tuple(sorted((str(k), int(v)) for k, v in e["flags"].items())),
         tuple(sorted((str(k), str(v)) for k, v in (e.get("bounds") or {}).items())))
        for e in rules
    )


def _known(flags: Mapping[str, Any]) -> dict[str, int]:
    fields = {f.name for f in dataclasses.fields(GameSettings)}
    return {str(k): int(v) for k, v in flags.items() if k in fields}


def decision_settings(base: GameSettings, rules: Sequence[Mapping[str, Any]], view: int) -> GameSettings:
    """The settings that decisions made while dynasty season ``view`` is the season in play run under: ``now`` / ``week`` flags
    from the moment of their event on, ``season`` flags once the season they were scheduled for is the one in play."""

    over: dict[str, int] = {}
    for entry in rules:
        bounds = entry.get("bounds") or {}
        for flag, value in _known(entry["flags"]).items():
            if bounds.get(flag, SEASON) in (NOW, WEEK) or int(entry["view_from"]) <= view:
                over[flag] = value
    return dataclasses.replace(base, **over) if over else base


def generation_settings(base: GameSettings, rules: Sequence[Mapping[str, Any]], season: int) -> GameSettings:
    """The settings dynasty season ``season``'s pool (aging, retirement, rookie class, depth charts) is generated under: every
    flag of every update whose first affected season is ``season`` or earlier."""

    over: dict[str, int] = {}
    for entry in rules:
        if int(entry["view_from"]) <= season:
            over.update(_known(entry["flags"]))
    return dataclasses.replace(base, **over) if over else base


def scheduled(rules: Iterable[Mapping[str, Any]]) -> set[str]:
    """Every flag some update already switched on (or scheduled): the update never offers it again."""

    return {flag for entry in rules for flag in entry["flags"]}


def pending_flags(base: GameSettings, rules: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """What a Realism update would switch on for this game: each registered flag that is below its target, applies to this
    game, and no earlier update already covers."""

    done = scheduled(rules)
    out = {}
    for flag, (target, _boundary) in UPGRADABLE_FLAGS.items():
        if flag in done or not hasattr(base, flag) or not applies(flag, base):
            continue
        if int(getattr(base, flag)) < target:
            out[flag] = target
    return out


def make_entry(flags: Mapping[str, int], *, seq: int, week: int, season_no: int, status: str, view_no: int) -> dict[str, Any]:
    """The settings-history row the fold records for an update (a pure function of the event and the state it lands on)."""

    return {
        "seq": int(seq), "week": int(week), "season_no": int(season_no), "status": str(status),
        "view_from": int(view_no) + 1,
        "flags": {str(k): int(v) for k, v in flags.items()},
        "bounds": {str(k): UPGRADABLE_FLAGS.get(k, (0, SEASON))[1] for k in flags},
    }


def rules_info(base: GameSettings, effective: GameSettings, rules: Sequence[Mapping[str, Any]], status: str, view_no: int) -> dict[str, Any]:
    """The ``rules`` block of a game payload: what is in force, what an update would turn on, and the history."""

    pend = pending_flags(base, rules)

    def row(flag: str, value: int, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        info = FLAGS.get(flag, {})
        boundary = UPGRADABLE_FLAGS.get(flag, (value, SEASON))[1]
        return {"flag": flag, "value": value, "label": info.get("label", flag), "body": info.get("body", ""),
                "boundary": boundary, "when": BOUNDARY_COPY[boundary], **(extra or {})}

    waiting = []
    for entry in rules:
        for flag, value in entry["flags"].items():
            if int(entry["view_from"]) > view_no and (entry.get("bounds") or {}).get(flag, SEASON) == SEASON:
                waiting.append(row(flag, int(value), {"from_view": int(entry["view_from"])}))
    return {
        "rules_version": len(rules),  # 0 = the game as it was created
        "eligible": bool(pend) and status != "complete",
        "pending": [row(f, v) for f, v in pend.items()],
        "scheduled": waiting,
        "in_force": {f: int(getattr(effective, f, 0) or 0) for f in UPGRADABLE_FLAGS if hasattr(effective, f)},
        "history": [{"seq": e["seq"], "week": e["week"], "season_no": e["season_no"], "flags": list(e["flags"])} for e in rules],
        "note": NOT_RETROACTIVE,
    }


__all__ = [
    "UPGRADABLE_FLAGS", "FLAGS", "BOUNDARIES", "BOUNDARY_COPY", "NOT_RETROACTIVE", "applies", "rules_key", "decision_settings",
    "generation_settings", "scheduled", "pending_flags", "make_entry", "rules_info",
]
