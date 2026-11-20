"""Real NFL game clock from ESPN's public scoreboard JSON.

``https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`` is a
free, unauthenticated, no-key endpoint (the same data espn.com renders). It
gives the real quarter, game clock, live score, final status and the current
down and distance for every game of the current NFL week. It is unofficial (no
published terms or SLA), the same risk class as the ESPN endpoint already read
by modules.public_roster_percentages; see docs/audits/2026-11-live-matchup-clock.md.

Server-side only: clients never call it. One payload is shared cluster-wide
(modules.sleeper_cache single-flight), cached 15-30s while games are live and
long (10 min) when none are. A generic User-Agent is sent, nothing personal.

It replaces two guesses on the Matchup screen: the 190-minute wall-clock
estimate of how much of a game is left, and the lagging nflverse "played" flag
for final. Best effort: any failure returns None and callers fall back to the
wall-clock estimate. Kill switch: ``DYNASTYGM_LIVE_REAL_CLOCK=0``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from modules.nfl_teams import canonical_team

logger = logging.getLogger(__name__)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
FLAG = "DYNASTYGM_LIVE_REAL_CLOCK"
USER_AGENT = "Mozilla/5.0 (compatible; scoreboard-reader)"
LIVE_TTL_SECONDS = 20.0
IDLE_TTL_SECONDS = 600.0
REGULATION_SECONDS = 3600.0
QUARTER_SECONDS = 900.0
# Overtime has no fixed length; a small positive share keeps the projection
# live (a started, unfinished game never reads as fully played).
OVERTIME_FRACTION_REMAINING = 0.03


_memo: dict[str, Any] = {"at": 0.0, "board": None}


def enabled() -> bool:
    return os.environ.get(FLAG, "1").strip().lower() not in {"0", "false", "off", "no"}


def fraction_remaining(period: int, clock_seconds: float, state: str, *, halftime: bool = False) -> float | None:
    """Regulation minutes left / 60, from the real quarter and clock."""

    if state == "post":
        return 0.0
    if state != "in":
        return None
    if halftime:
        return 0.5
    if period >= 5:
        return OVERTIME_FRACTION_REMAINING
    if period < 1:
        return None
    clock = max(0.0, min(QUARTER_SECONDS, float(clock_seconds)))
    left = (4 - period) * QUARTER_SECONDS + clock
    return round(max(0.0, min(1.0, left / REGULATION_SECONDS)), 4)


def clock_label(period: int, display_clock: str, state: str, *, halftime: bool = False) -> str | None:
    if state == "post":
        return "Final"
    if state != "in":
        return None
    if halftime:
        return "Half"
    if period >= 5:
        return f"OT {display_clock}".strip()
    return f"Q{period} {display_clock}".strip()


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_scoreboard(payload: Any) -> dict[str, Any] | None:
    """``{"week": int|None, "teams": {TEAM: info}}`` from the raw ESPN payload."""

    if not isinstance(payload, dict):
        return None
    week = (payload.get("week") or {}).get("number")
    teams: dict[str, Any] = {}
    for event in payload.get("events") or []:
        try:
            comp = (event.get("competitions") or [None])[0] or {}
            status = event.get("status") or comp.get("status") or {}
            stype = status.get("type") or {}
            state = str(stype.get("state") or "")
            name = str(stype.get("name") or "")
            halftime = name == "STATUS_HALFTIME"
            period = int(status.get("period") or 0)
            clock = float(status.get("clock") or 0.0)
            display = str(status.get("displayClock") or "")
            competitors = {str(c.get("homeAway")): c for c in comp.get("competitors") or []}
            home, away = competitors.get("home"), competitors.get("away")
            if not home or not away:
                continue
            situation = comp.get("situation") or {}
            frac = fraction_remaining(period, clock, state, halftime=halftime)
            label = clock_label(period, display, state, halftime=halftime)
            for side, other, is_home in ((home, away, True), (away, home, False)):
                code = canonical_team((side.get("team") or {}).get("abbreviation"))
                opp = canonical_team((other.get("team") or {}).get("abbreviation"))
                if not code:
                    continue
                poss_id = str(situation.get("possession") or "")
                teams[code] = {
                    "state": state,  # pre | in | post
                    "status_name": name,
                    "delayed": "DELAY" in name or "SUSPEND" in name,
                    "fraction_remaining": frac,
                    "label": label,
                    "period": period,
                    "is_home": is_home,
                    "opponent": opp,
                    "team_score": _int(side.get("score")),
                    "opponent_score": _int(other.get("score")),
                    "situation": (
                        (str(situation.get("downDistanceText") or "") or None) if state == "in" and not halftime else None
                    ),
                    "has_ball": bool(poss_id) and poss_id == str((side.get("team") or {}).get("id") or ""),
                }
        except Exception:  # noqa: BLE001 - one bad event never drops the board
            logger.debug("scoreboard event skipped", exc_info=True)
    return {"week": int(week) if isinstance(week, (int, float)) else None, "teams": teams}


def _fetch() -> Any:
    import requests

    response = requests.get(SCOREBOARD_URL, timeout=5, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.json()


def current_board() -> dict[str, Any] | None:
    """Parsed scoreboard cached for the live TTL, or None when disabled or unavailable."""

    if not enabled():
        return None
    now = time.monotonic()
    if _memo["board"] is not None and now - _memo["at"] < 3.0:
        return _memo["board"]  # one request reads many starters
    board = _current_board_uncached()
    _memo.update(at=now, board=board)
    return board


def _current_board_uncached() -> dict[str, Any] | None:
    try:
        from modules import live_policy, sleeper_cache

        live = live_policy.is_live()
        ttl = LIVE_TTL_SECONDS if live else IDLE_TTL_SECONDS
        payload = sleeper_cache.shared_json(
            SCOREBOARD_URL,
            ttl=ttl,
            fetch=_fetch,
            store_ttl=max(ttl * 4, 300.0),
            max_age_on_error=max(ttl * 3, 90.0),
        )
        return parse_scoreboard(payload)
    except Exception:  # noqa: BLE001 - best effort; wall-clock fallback
        logger.debug("scoreboard unavailable", exc_info=True)
        return None


def team_info(board: dict[str, Any] | None, team: Any, week: int | None) -> dict[str, Any] | None:
    """This team's game on the board, only when the board is for ``week``."""

    if not board or not team:
        return None
    if board.get("week") is not None and week is not None and int(board["week"]) != int(week):
        return None
    return (board.get("teams") or {}).get(canonical_team(team))
