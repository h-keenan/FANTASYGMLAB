"""Direction check-in: a few times a season, ask whether the team's declared
direction still fits. Pure functions, no I/O, no football compute.

The direction is the existing Team Situation setting (``modules.team_stance``:
Rebuilding / Balanced / Competing, which drives Rebuild / Retool / Contend
valuations). This module only decides WHEN to ask and what to say; the answer
goes back through the normal Team Situation write, so there is no second copy
of the setting.

Decision, in order, each stage recording a ``reason`` when it says no so the
result is auditable (same shape as ``modules.notification_decider``):

1. ``not_in_season``   - the league is not in season, or its week is unknown.
2. ``no_direction_set``- nothing declared: the Team Situation screen is where
                         a first choice is made; this never nags for one.
3. ``no_moment``       - this week is not inside a check-in window.
4. ``already_handled`` - this season's window for this moment was already
                         answered or dismissed (any answer ends it for the
                         season: a dismissal is final, never a nag loop).
5. ``rate_limited``    - something was answered/dismissed less than
                         ``RATE_LIMIT_DAYS`` ago, whatever the moment.

Moments (weeks are league weeks; windows never overlap, the earlier name wins):
``season_start`` (weeks 1-2), ``trade_deadline`` (the week before the
league's trade deadline through the deadline week, when it has one),
``playoff_push`` (the last three regular-season weeks), ``midseason`` (the
two weeks around the halfway point). At most four prompts a season, one per
moment, never closer than two weeks apart.

Storage: the existing ``user_settings.settings`` JSON under ``direction_checkin``
(per league, ``{moment_key: {"at": iso, "action": ...}}``), the same table the
notification preferences use, so there is nothing to migrate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

SETTINGS_KEY = "direction_checkin"

MOMENT_SEASON_START = "season_start"
MOMENT_MIDSEASON = "midseason"
MOMENT_TRADE_DEADLINE = "trade_deadline"
MOMENT_PLAYOFF_PUSH = "playoff_push"
MOMENTS = (MOMENT_SEASON_START, MOMENT_MIDSEASON, MOMENT_TRADE_DEADLINE, MOMENT_PLAYOFF_PUSH)
MOMENT_LABELS = {
    MOMENT_SEASON_START: "Start of the season",
    MOMENT_MIDSEASON: "Midseason",
    MOMENT_TRADE_DEADLINE: "Trade deadline",
    MOMENT_PLAYOFF_PUSH: "Playoff push",
}

ACTION_KEPT = "kept"
ACTION_CHANGED = "changed"
ACTION_DISMISSED = "dismissed"
ACTIONS = (ACTION_KEPT, ACTION_CHANGED, ACTION_DISMISSED)

RATE_LIMIT_DAYS = 14
IN_SEASON_STATUSES = frozenset({"in_season", "post_season"})
DEFAULT_PLAYOFF_WEEK_START = 15
SEASON_START_LAST_WEEK = 2
PLAYOFF_PUSH_WEEKS = 3
MAX_RECORDS_PER_LEAGUE = 12
MAX_LEAGUES = 100

REASON_NOT_IN_SEASON = "not_in_season"
REASON_NO_DIRECTION = "no_direction_set"
REASON_NO_MOMENT = "no_moment"
REASON_ALREADY_HANDLED = "already_handled"
REASON_RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class Decision:
    show: bool
    moment: str = ""
    moment_key: str = ""
    # "" when the prompt should show, else why it should not.
    reason: str = ""


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def regular_season_end(playoff_week_start: Any) -> int:
    """Last regular-season week (Sleeper's playoffs start the week after)."""

    return max(4, (_int(playoff_week_start) or DEFAULT_PLAYOFF_WEEK_START) - 1)


def windows(playoff_week_start: Any = None, trade_deadline: Any = None) -> dict[str, tuple[int, int]]:
    """Inclusive (first, last) league weeks of each moment, trimmed so no week
    belongs to two moments: the start of the season, the trade deadline and the
    playoff push (all time-critical) keep their weeks; midseason, the softest
    ask, gives way."""

    end = regular_season_end(playoff_week_start)
    out: dict[str, tuple[int, int]] = {}
    out[MOMENT_SEASON_START] = (1, min(SEASON_START_LAST_WEEK, end))
    deadline = _int(trade_deadline)
    if deadline is not None and deadline < 18:  # Sleeper uses 99 for "no deadline"
        out[MOMENT_TRADE_DEADLINE] = (max(SEASON_START_LAST_WEEK + 1, deadline - 1), min(deadline, end))
    push_first = max(SEASON_START_LAST_WEEK + 1, end - PLAYOFF_PUSH_WEEKS + 1)
    out[MOMENT_PLAYOFF_PUSH] = (push_first, end)
    mid = (end + 1) // 2
    out[MOMENT_MIDSEASON] = (mid, mid + 1)
    # Resolve overlaps: season start, then the deadline, then the playoff push
    # keep their weeks; midseason (the softest ask) gives way.
    taken: set[int] = set()
    resolved: dict[str, tuple[int, int]] = {}
    for moment in (MOMENT_SEASON_START, MOMENT_TRADE_DEADLINE, MOMENT_PLAYOFF_PUSH, MOMENT_MIDSEASON):
        if moment not in out:
            continue
        first, last = out[moment]
        weeks = [w for w in range(first, last + 1) if w not in taken]
        if not weeks:
            continue
        taken.update(weeks)
        resolved[moment] = (min(weeks), max(weeks))
    return resolved


def moment_for_week(week: int, playoff_week_start: Any = None, trade_deadline: Any = None) -> str:
    """The check-in moment a league week falls in, or "" when none."""

    for moment, (first, last) in windows(playoff_week_start, trade_deadline).items():
        if first <= week <= last:
            return moment
    return ""


def moment_key(season: Any, moment: str) -> str:
    return f"{int(_int(season) or 0)}:{moment}"


def valid_moment_key(value: Any) -> bool:
    season, _, moment = str(value or "").partition(":")
    return season.isdigit() and len(season) == 4 and moment in MOMENTS


def decide(
    *,
    league_status: Any,
    season: Any,
    week: Any,
    stance: Any,
    handled: Mapping[str, Any] | None,
    now: datetime,
    playoff_week_start: Any = None,
    trade_deadline: Any = None,
) -> Decision:
    """Should the Dashboard ask about direction right now? See the module
    docstring for the stages. ``handled`` is this league's stored records
    (``{moment_key: {"at": iso, "action": str}}``)."""

    wk = _int(week)
    if str(league_status or "").strip().lower() not in IN_SEASON_STATUSES or wk is None:
        return Decision(False, reason=REASON_NOT_IN_SEASON)
    if not str(stance or "").strip():
        return Decision(False, reason=REASON_NO_DIRECTION)
    moment = moment_for_week(wk, playoff_week_start, trade_deadline)
    if not moment:
        return Decision(False, reason=REASON_NO_MOMENT)
    key = moment_key(season, moment)
    records = handled if isinstance(handled, Mapping) else {}
    if key in records:
        return Decision(False, moment, key, REASON_ALREADY_HANDLED)
    latest = max(
        (t for t in (_as_utc((r or {}).get("at")) for r in records.values() if isinstance(r, Mapping)) if t is not None),
        default=None,
    )
    if latest is not None and now - latest < timedelta(days=RATE_LIMIT_DAYS):
        return Decision(False, moment, key, REASON_RATE_LIMITED)
    return Decision(True, moment, key, "")


# ----------------------------------------------------------------- copy

_BODY = {
    MOMENT_SEASON_START: "The season is underway. Does {label} still describe your team, or has your outlook changed since you set it?",
    MOMENT_MIDSEASON: "You are about halfway through. Does {label} still describe your team, or has the season changed your outlook?",
    MOMENT_TRADE_DEADLINE: "Your trade deadline is close, the last chance to move players. Does {label} still describe your team?",
    MOMENT_PLAYOFF_PUSH: "The playoffs are close. Does {label} still describe your team, or is it time to shift gears?",
}


def copy_for(moment: str, stance_label: str) -> dict[str, str]:
    """The words web and mobile render verbatim. Headline names the moment;
    the body names the current direction and says what the answer does."""

    label = stance_label or "your direction"
    body = _BODY.get(moment, _BODY[MOMENT_MIDSEASON]).format(label=label)
    return {
        "headline": f"{MOMENT_LABELS.get(moment, 'Check-in')}: still {label}?",
        "body": f"{body} It shapes the trades and values we show you.",
        "keep_label": "Still fits",
        "dismiss_label": "Not now",
    }


# ------------------------------------------------------------- storage

def handled_for_league(settings: Mapping[str, Any] | None, league_id: str) -> dict[str, dict[str, str]]:
    """This league's records from a ``user_settings.settings`` blob, cleaned."""

    root = (settings or {}).get(SETTINGS_KEY) if isinstance(settings, Mapping) else None
    league = root.get(str(league_id)) if isinstance(root, Mapping) else None
    out: dict[str, dict[str, str]] = {}
    if isinstance(league, Mapping):
        for key, record in league.items():
            if valid_moment_key(key) and isinstance(record, Mapping) and _as_utc(record.get("at")) is not None:
                action = str(record.get("action") or "")
                out[str(key)] = {"at": str(record["at"]), "action": action if action in ACTIONS else ACTION_DISMISSED}
    return out


def validate_action(action: Any, key: Any) -> str:
    """"" when the answer is acceptable, else a client-safe message."""

    if action not in ACTIONS:
        return "action must be one of: " + ", ".join(ACTIONS)
    if not valid_moment_key(key):
        return "moment_key is not a valid check-in moment."
    return ""


def record_answer(
    settings: Mapping[str, Any] | None, league_id: str, key: str, action: str, now: datetime
) -> dict[str, Any]:
    """A copy of ``settings`` with the answer recorded for this league. Keeps
    the newest ``MAX_RECORDS_PER_LEAGUE`` records and ``MAX_LEAGUES`` leagues
    so the blob cannot grow without bound; every other setting is untouched."""

    out = dict(settings or {})
    root = dict(out.get(SETTINGS_KEY) or {}) if isinstance(out.get(SETTINGS_KEY), Mapping) else {}
    records = handled_for_league(out, league_id)
    records[key] = {"at": now.astimezone(timezone.utc).isoformat(), "action": action}
    newest = sorted(records.items(), key=lambda kv: _as_utc(kv[1]["at"]) or now, reverse=True)[:MAX_RECORDS_PER_LEAGUE]
    root[str(league_id)] = dict(newest)
    if len(root) > MAX_LEAGUES:
        stamp = lambda lid: max((_as_utc(r.get("at")) or now for r in root[lid].values()), default=now)  # noqa: E731
        for lid in sorted(root, key=stamp)[: len(root) - MAX_LEAGUES]:
            del root[lid]
    out[SETTINGS_KEY] = root
    return out


__all__ = [
    "SETTINGS_KEY", "MOMENTS", "MOMENT_LABELS", "ACTIONS", "RATE_LIMIT_DAYS", "Decision", "windows",
    "moment_for_week", "moment_key", "valid_moment_key", "decide", "copy_for", "handled_for_league",
    "validate_action", "record_answer",
]
