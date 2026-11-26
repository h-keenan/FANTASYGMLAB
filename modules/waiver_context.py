"""Waiver context that the lineup-need model does not see: injury/handcuff
links to the user's own players, and the real NFL schedule (byes, the
fantasy-playoff stretch).

Pure functions over data the waiver pipeline already holds (the user's roster
frame, the free-agent frame, ``modules.nfl_schedule`` rows and the
points-allowed-by-position tiers). Nothing here invents a number: a link or note
is emitted only when the rows that produce it are present.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from modules import injury_status
from modules.coerce import float_nan_to_none

# Positions where "the player directly behind my guy" is a real depth-chart idea.
_BACKUP_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})
# Only running backs have a handcuff relationship that moves lineups.
_HANDCUFF_POSITIONS = frozenset({"RB"})
HANDCUFF_LABELS = frozenset({"handcuff", "backup with upside", "committee back"})
# A roster player counts as a "stud" worth insuring at this overall rating, the
# same absolute bar the elite-wire test uses (modules.waivers_logic).
STUD_MIN_OVERALL_RATING = 72
# Without ratings: the roster's top scorers at the position.
_STUD_TOP_N = 2
# How many weeks before the fantasy playoffs the "playoff push" framing starts.
PLAYOFF_PUSH_LEAD_WEEKS = 4
DEFAULT_PLAYOFF_WEEK_START = 15
_BYE_LOOKAHEAD_WEEKS = 2


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    return str(value).strip()


def _is_out(row: Mapping[str, Any]) -> bool:
    cls = injury_status.classify(_text(row.get("status")), _text(row.get("injury_status")))
    return bool(cls.ruled_out or cls.p_play <= injury_status.LIKELY_OUT_P_PLAY)


def _studs(roster_rows: list[dict[str, Any]], score_field: str) -> set[int]:
    """Indexes (into ``roster_rows``) of the roster's players worth insuring or covering."""

    by_pos: dict[str, list[tuple[float, int]]] = {}
    studs: set[int] = set()
    for i, row in enumerate(roster_rows):
        pos = _text(row.get("position")).upper()
        score = float_nan_to_none(row.get(score_field)) or 0.0
        by_pos.setdefault(pos, []).append((score, i))
        rating = float_nan_to_none(row.get("_overall_rating_col"))
        if rating is None:
            rating = float_nan_to_none(row.get("overall_rating"))
        if rating is not None and rating >= STUD_MIN_OVERALL_RATING and score > 0:
            studs.add(i)
    if not studs:
        for entries in by_pos.values():
            for score, i in sorted(entries, reverse=True)[:_STUD_TOP_N]:
                if score > 0:
                    studs.add(i)
    return studs


def insurance_links(
    candidates: pd.DataFrame,
    roster_df: pd.DataFrame | None,
    score_field: str,
) -> dict[str, dict[str, str]]:
    """``player_id -> {"kind", "player", "position"}`` for wire players tied to the user's own roster.

    * ``injured_backup``: a same-team, same-position free agent behind one of the
      user's relevant players who is ruled out (a starter just went down: the
      player who inherits the work is the highest-upside add on the wire).
    * ``handcuff``: a same-team running back behind one of the user's healthy
      studs (insurance for an asset the user cannot replace from the wire).

    Both need real team and position data on both frames, and the candidate
    must score below the player he backs up.
    """

    if (
        candidates is None
        or candidates.empty
        or roster_df is None
        or roster_df.empty
        or not {"team", "position", "player_id"}.issubset(candidates.columns)
        or not {"team", "position"}.issubset(roster_df.columns)
    ):
        return {}
    roster_rows = roster_df.to_dict("records")
    studs = _studs(roster_rows, score_field)
    by_team_pos: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    for i, row in enumerate(roster_rows):
        team = _text(row.get("team")).upper()
        pos = _text(row.get("position")).upper()
        if team and team not in {"FA", "FREE AGENT"} and pos in _BACKUP_POSITIONS:
            by_team_pos.setdefault((team, pos), []).append((i, row))
    if not by_team_pos:
        return {}

    cand_rows = candidates.to_dict("records")
    # The best wire player behind each team's back: the direct backup, not every body.
    top_wire: dict[tuple[str, str], float] = {}
    for row in cand_rows:
        key = (_text(row.get("team")).upper(), _text(row.get("position")).upper())
        top_wire[key] = max(top_wire.get(key, 0.0), float_nan_to_none(row.get(score_field)) or 0.0)

    out: dict[str, dict[str, str]] = {}
    for row in cand_rows:
        team = _text(row.get("team")).upper()
        pos = _text(row.get("position")).upper()
        pid = _text(row.get("player_id"))
        score = float_nan_to_none(row.get(score_field)) or 0.0
        mine = by_team_pos.get((team, pos))
        if not mine or not pid or score <= 0:
            continue
        ahead = [(i, r) for i, r in mine if (float_nan_to_none(r.get(score_field)) or 0.0) > score]
        if not ahead:
            continue
        injured = [(i, r) for i, r in ahead if i in studs and _is_out(r)]
        if injured:
            _i, r = max(injured, key=lambda e: float_nan_to_none(e[1].get(score_field)) or 0.0)
            out[pid] = {"kind": "injured_backup", "player": _text(r.get("name")), "position": pos}
            continue
        if pos in _HANDCUFF_POSITIONS:
            healthy_studs = [(i, r) for i, r in ahead if i in studs and not _is_out(r)]
            labelled = _text(row.get("opportunity_label")).casefold() in HANDCUFF_LABELS
            direct = score >= top_wire.get((team, pos), 0.0)
            if healthy_studs and (labelled or direct):
                _i, r = max(healthy_studs, key=lambda e: float_nan_to_none(e[1].get(score_field)) or 0.0)
                out[pid] = {"kind": "handcuff", "player": _text(r.get("name")), "position": pos}
    return out


def annotate_insurance(candidates: pd.DataFrame, roster_df: pd.DataFrame | None, score_field: str) -> pd.DataFrame:
    """Add ``injury_cover_for`` / ``handcuff_of`` (the user's player's name, else "")."""

    links = insurance_links(candidates, roster_df, score_field)
    out = candidates.copy()
    pids = out["player_id"].astype(str) if "player_id" in out.columns else pd.Series("", index=out.index)
    out["injury_cover_for"] = [links.get(p, {}).get("player", "") if links.get(p, {}).get("kind") == "injured_backup" else "" for p in pids]
    out["handcuff_of"] = [links.get(p, {}).get("player", "") if links.get(p, {}).get("kind") == "handcuff" else "" for p in pids]
    return out


def playoff_week_start(league: Mapping[str, Any] | None) -> int:
    try:
        value = int(((league or {}).get("settings") or {}).get("playoff_week_start") or 0)
    except (TypeError, ValueError):
        value = 0
    return value if value > 0 else DEFAULT_PLAYOFF_WEEK_START


def late_season(week: int, playoff_start: int) -> bool:
    """True from a few weeks before the fantasy playoffs through the bracket."""

    return week > 0 and week >= playoff_start - PLAYOFF_PUSH_LEAD_WEEKS


def schedule_facts(
    schedule: list[Mapping[str, Any]],
    *,
    week: int,
    playoff_start: int,
    position: str = "",
    defense_strength: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Bye and playoff-stretch facts for one NFL team's real schedule rows.

    Returns ``bye_week`` (int|None), ``on_bye_now``, ``playoff_edge`` (soft minus
    tough opponents at the position across the fantasy playoff weeks, 0 when no
    tier data) and ``schedule_note`` (one honest sentence, "" when nothing
    notable)."""

    bye_week = next((int(r["week"]) for r in schedule if r.get("bye")), None)
    on_bye_now = bool(bye_week is not None and week > 0 and bye_week == week)
    notes: list[str] = []
    if on_bye_now:
        notes.append(f"on bye in week {week}, so no points until week {week + 1}")
    elif bye_week is not None and week > 0 and week < bye_week <= week + _BYE_LOOKAHEAD_WEEKS:
        notes.append(f"bye in week {bye_week}")

    edge = 0
    if week > 0 and late_season(week, playoff_start) and defense_strength:
        soft = tough = 0
        weeks_seen: list[str] = []
        for r in schedule:
            w = int(r.get("week") or 0)
            if r.get("bye") or w < playoff_start or w > playoff_start + 2:
                continue
            opp = _text(r.get("opponent")).upper()
            tier = _text(((defense_strength.get(opp) or {}).get(position.upper()) or {}).get("tier")).casefold()
            if tier == "weak":
                soft += 1
                weeks_seen.append(f"{opp} wk {w}")
            elif tier == "tough":
                tough += 1
        edge = soft - tough
        if soft >= 2 and tough == 0:
            notes.append("soft playoff-week matchups (" + ", ".join(weeks_seen[:3]) + ")")
        elif tough >= 2 and soft == 0:
            notes.append("tough run of playoff-week defenses")
    return {
        "bye_week": bye_week,
        "on_bye_now": on_bye_now,
        "playoff_edge": edge,
        "late_season": late_season(week, playoff_start),
        "schedule_note": "; ".join(notes),
    }


def annotate_schedule(
    candidates: pd.DataFrame,
    league: Mapping[str, Any] | None,
    *,
    season: int,
    games: pd.DataFrame | None = None,
    defense_strength: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None,
) -> pd.DataFrame:
    """Add ``bye_week`` / ``on_bye_now`` / ``playoff_edge`` / ``schedule_note``.

    A no-op copy when the league has no live week (offseason) or no schedule."""

    from modules import league_calendar, nfl_schedule

    out = candidates.copy()
    try:
        week = int(((league or {}).get("settings") or {}).get("leg") or 0)
    except (TypeError, ValueError):
        week = 0
    if week <= 0 or league_calendar.is_offseason(league) or "team" not in out.columns:
        return out
    playoff_start = playoff_week_start(league)
    games_df = games if games is not None else nfl_schedule.load_games()
    cache: dict[tuple[str, str], dict[str, Any]] = {}
    rows = []
    for team, pos in zip(out["team"].fillna("").astype(str), out.get("position", pd.Series("", index=out.index)).fillna("").astype(str)):
        key = (team.upper(), pos.upper())
        if key not in cache:
            schedule = nfl_schedule.team_schedule(team, season, games=games_df) if team else []
            cache[key] = schedule_facts(
                schedule, week=week, playoff_start=playoff_start, position=pos, defense_strength=defense_strength
            )
        rows.append(cache[key])
    facts = pd.DataFrame(rows, index=out.index)
    for col in facts.columns:
        out[col] = facts[col]
    return out
