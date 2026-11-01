"""This-week starting-lineup impact of a proposed trade.

The season-value lineup the fit engine uses ("who are this roster's
starters") deliberately ignores byes and injuries: it restores injured
players to their healthy value so the injury model can price the missed
weeks separately. That is right for long-run value, but it hides the
question a manager asks first when trading a starter away: "can I still
field a lineup THIS WEEK?"

This module answers exactly that, from the same weekly lineup builder the
Matchup screen uses (``team_eval.suggest_optimal_lineup`` weekly mode): a
player on bye or ruled out (Out/IR/PUP/Suspended) is never slotted, so a
dedicated slot nothing else can fill stays open. It compares the roster
before and after the trade and reports, per position, how many startable
players remain, which dedicated slots go (or stay) empty, and whether the
only players left are injury-designated (Questionable/Doubtful).

Trade engine v2 (docs/trade-engine-v2.md): the SCORE no longer reads this
module. ``modules.trade_lineup_model`` prices lineup holes, byes, injuries and
waiver replacement in expected points. This module stays for what it states
as fact (this week's startable counts and the "no startable RB" headline the
UI shows as a warning), so the warning list and the score cannot drift apart
on facts, only the score carries the cost.

Pure: no I/O beyond the cached NFL schedule lookup for byes (failures read
as "no bye", never invented). Offseason (no fantasy week) returns
``available: False`` so nothing here is ever claimed out of season.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

import pandas as pd

from modules import nfl_schedule
from modules.rankings import injury_level, is_ruled_out
from modules.team_eval import _lineup_slots, lineup_open_slots, suggest_optimal_lineup

DEDICATED_POSITIONS = ("QB", "RB", "WR", "TE")

SEVERITY_CRITICAL = "critical"
SEVERITY_WARN = "warn"


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def bye_player_ids(df: pd.DataFrame, week: int, season: int | None = None) -> set[str]:
    """Players whose NFL team has its bye in ``week`` (schedule-backed only)."""

    if df is None or df.empty or "player_id" not in df.columns or "team" not in df.columns or week <= 0:
        return set()
    season = season or date.today().year
    by_team: dict[str, bool] = {}
    out: set[str] = set()
    for pid, team in zip(df["player_id"].astype(str).tolist(), df["team"].tolist()):
        code = _text(team).upper()
        if not code or not pid:
            continue
        if code not in by_team:
            try:
                by_team[code] = nfl_schedule.team_bye_week(code, season) == week
            except Exception:
                by_team[code] = False
        if by_team[code]:
            out.add(pid)
    return out


def _position_pool(df: pd.DataFrame, byes: set[str]) -> dict[str, dict[str, Any]]:
    """Per position: startable count, and how many of those are injury-designated."""

    pool = {pos: {"startable": 0, "designated": 0, "bye": 0, "out": 0, "names": []} for pos in DEDICATED_POSITIONS}
    if df is None or df.empty or "position" not in df.columns:
        return pool
    for _, row in df.iterrows():
        pos = _text(row.get("position")).upper()
        if pos not in pool:
            continue
        pid = _text(row.get("player_id"))
        status, injury = _text(row.get("status")), _text(row.get("injury_status"))
        if pid in byes:
            pool[pos]["bye"] += 1
        elif is_ruled_out(status, injury):
            pool[pos]["out"] += 1
        else:
            pool[pos]["startable"] += 1
            if injury_level(status, injury) != "healthy":
                pool[pos]["designated"] += 1
            pool[pos]["names"].append(_text(row.get("name")))
    return pool


def _multiset_new(after: Iterable[str], before: Iterable[str]) -> list[str]:
    remaining = list(before)
    new: list[str] = []
    for slot in after:
        if slot in remaining:
            remaining.remove(slot)
        else:
            new.append(slot)
    return new


_BEFORE_STATE_CACHE: list[tuple[tuple, pd.DataFrame, dict[str, Any]]] = []
_BEFORE_STATE_CACHE_MAX = 4


def _before_state(
    before_df: pd.DataFrame,
    settings: dict[str, Any] | None,
    current_week: int,
    score_field: str,
    season: int | None,
) -> dict[str, Any]:
    """The before-trade half of the comparison, memoized per roster frame.

    Grading many packages for one roster (Trade Hub's gate) repeats exactly
    this half for every package; it depends only on the roster, the league
    settings, the week and the score column. The frame is held so its ``id``
    cannot be reused while the entry lives. Callers must treat the result as
    read-only."""

    key = (id(before_df), len(before_df), int(current_week), score_field, season, repr(sorted((str(k), repr(v)) for k, v in (settings or {}).items())))
    for entry_key, _frame, state in _BEFORE_STATE_CACHE:
        if entry_key == key:
            return state
    byes = bye_player_ids(before_df, current_week, season)
    lineup = suggest_optimal_lineup(before_df, settings, score_field=score_field, bye_player_ids=byes)
    state = {
        "byes": byes,
        "open": lineup_open_slots(lineup, settings),
        "pool": _position_pool(before_df, byes),
    }
    _BEFORE_STATE_CACHE.append((key, before_df, state))
    del _BEFORE_STATE_CACHE[:-_BEFORE_STATE_CACHE_MAX]
    return state


def weekly_lineup_impact(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    lineup_settings: Mapping[str, Any] | None,
    *,
    current_week: int,
    in_season: bool,
    score_field: str,
    season: int | None = None,
) -> dict[str, Any]:
    """Compare this week's startable lineup before vs after the trade."""

    if not in_season or current_week <= 0 or before_df is None or before_df.empty:
        return {"available": False, "warnings": [], "new_open_slots": [], "week": 0}

    settings = dict(lineup_settings) if lineup_settings else None
    slots = _lineup_slots(settings)
    before_state = _before_state(before_df, settings, current_week, score_field, season)
    byes_after = bye_player_ids(after_df, current_week, season)
    after_lineup = suggest_optimal_lineup(
        after_df if after_df is not None else before_df.iloc[0:0],
        settings,
        score_field=score_field,
        bye_player_ids=byes_after,
    )
    open_before = list(before_state["open"])
    open_after = lineup_open_slots(after_lineup, settings)
    new_open = _multiset_new(open_after, open_before)

    pool_before = before_state["pool"]
    pool_after = _position_pool(after_df, byes_after)

    warnings: list[dict[str, Any]] = []
    for pos in DEDICATED_POSITIONS:
        needed = int(slots.get(pos, 0) or 0)
        if needed <= 0:
            continue
        b, a = pool_before[pos], pool_after[pos]
        worse = a["startable"] < b["startable"]
        more_injured = a["startable"] > 0 and a["designated"] == a["startable"] and b["designated"] < b["startable"]
        if not (worse or more_injured):
            continue
        if a["startable"] == 0:
            warnings.append(
                {
                    "code": "no_startable_position",
                    "position": pos,
                    "severity": SEVERITY_CRITICAL,
                    "startable_before": b["startable"],
                    "startable_after": 0,
                    "slots": needed,
                    "headline": f"Leaves you without a startable {pos} in Week {current_week}",
                    "detail": (
                        f"You have {b['startable']} startable {pos}{'s' if b['startable'] != 1 else ''} now and "
                        f"{needed} {pos} slot{'s' if needed != 1 else ''} to fill; after this trade none would "
                        f"be left that is healthy and not on a bye."
                    ),
                }
            )
        elif worse and a["startable"] < needed:
            warnings.append(
                {
                    "code": "thin_position",
                    "position": pos,
                    "severity": SEVERITY_WARN,
                    "startable_before": b["startable"],
                    "startable_after": a["startable"],
                    "slots": needed,
                    "headline": f"Leaves a {pos} slot to fill in Week {current_week}",
                    "detail": (
                        f"Only {a['startable']} startable {pos}{'s' if a['startable'] != 1 else ''} would remain "
                        f"for {needed} {pos} slots, so one slot falls to a flex or stays empty."
                    ),
                }
            )
        elif a["designated"] == a["startable"]:
            warnings.append(
                {
                    "code": "only_injured_position",
                    "position": pos,
                    "severity": SEVERITY_WARN,
                    "startable_before": b["startable"],
                    "startable_after": a["startable"],
                    "slots": needed,
                    "headline": f"Every {pos} you'd have left carries an injury designation",
                    "detail": (
                        f"All {a['startable']} remaining startable {pos}{'s' if a['startable'] != 1 else ''} "
                        "are listed Questionable/Doubtful, so your lineup depends on game-day news."
                    ),
                }
            )

    return {
        "available": True,
        "week": int(current_week),
        "open_slots_before": open_before,
        "open_slots_after": open_after,
        "new_open_slots": new_open,
        "startable_before": {pos: pool_before[pos]["startable"] for pos in DEDICATED_POSITIONS},
        "startable_after": {pos: pool_after[pos]["startable"] for pos in DEDICATED_POSITIONS},
        "warnings": warnings,
    }
