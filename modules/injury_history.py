"""Point-in-time injury history: change events + twice-weekly snapshots.

Why: ``data/players.db`` only ever holds the *current* ``injury_status``
(overwritten every 30 minutes by scripts/sync_injury_status.py), so the repo
had no way to answer "when did he get hurt, how long was he out, did it come
back" or to separate injuries from benching/rest (docs/audits/
2026-11-sim-projection-audit.md section 4.4). This module records history
alongside that overwrite and never touches players.db.

Storage (append-only CSV under ``data/injury_history/``, committed by the
sync workflow in the same commit as its players.db patch):

* ``events_<season>.csv``     one row per CHANGE of a tracked player's
                              (status, injury_status, body part, practice
                              status) tuple. A recovery is an event too (empty
                              injury fields, status Active), so durations are
                              ``next event - this event``.
* ``snapshots_<season>.csv``  twice a week in season (Tuesday after Monday
                              night, Friday after the final designations) the
                              full list of tracked players that are NOT fully
                              healthy. A player absent from a snapshot that
                              exists in ``snapshot_index.csv`` was healthy.
* ``snapshot_index.csv``      one row per snapshot taken (dedupe + the proof
                              that an absence means "healthy", not "not
                              captured").

Size (measured on 2026-11 data): ~200 tracked non-healthy players. Events are
a few hundred rows/week in season, snapshots ~200 rows x 2/week: together about
1-2 MB per season uncompressed, and plain appends delta-compress well in git.
The official weekly practice reports live in a separate file
(modules/nflverse_injury_reports.py).

Pure logic (state extraction, change detection, slot scheduling, CSV
serialisation) is separated from file I/O so it can be tested without any
network. Never raises into the caller's production job: ``capture`` returns a
result dict and the sync script treats failure as "skip history this run".
"""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

HISTORY_DIR = Path("data") / "injury_history"
DISABLE_ENV = "INJURY_HISTORY_DISABLE"

SOURCE_LIVE = "sleeper_live"
SOURCE_SNAPSHOT = "sleeper_snapshot"

# Skill positions + kickers: the players the sim/projections care about and
# the ones whose designations matter for fantasy. IDP is deliberately left out
# to keep the files small; add positions here to widen it.
TRACKED_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "K"})

HEALTHY_STATUSES = frozenset({"", "active"})

EVENT_COLUMNS = (
    "captured_at", "season", "week", "player_id", "team", "position",
    "status", "injury_status", "body_part", "practice", "practice_desc", "source",
)
SNAPSHOT_COLUMNS = ("snapshot_key",) + EVENT_COLUMNS
INDEX_COLUMNS = ("snapshot_key", "captured_at", "season", "week", "tracked_players", "rows")

# A Sleeper dump with fewer players than this is a failed/poisoned fetch, never
# a real roster universe (the real dump is ~10k+). Record nothing from it.
MIN_PLAYERS_IN_DUMP = 2000
# Circuit breakers against a poisoned dump flipping everyone at once.
MAX_EVENTS_PER_RUN = 1500
MAX_EVENTS_FIRST_RUN = 3000

# Snapshot slots, UTC: (weekday Mon=0, hour, name).
SNAPSHOT_SLOTS = ((1, 14, "tue"), (4, 21, "fri"))
# A missed slot is only caught up within this window; older ones are skipped
# rather than recorded with a misleading timestamp.
SNAPSHOT_CATCHUP = timedelta(hours=30)


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "nan", "null"} else text


@dataclass(frozen=True)
class PlayerState:
    status: str
    injury_status: str
    body_part: str
    practice: str
    practice_desc: str
    team: str
    position: str

    def key(self) -> tuple[str, str, str, str]:
        """The tuple whose change constitutes an event."""

        return (self.status, self.injury_status, self.body_part, self.practice)

    @property
    def healthy(self) -> bool:
        return self.status.lower() in HEALTHY_STATUSES and not self.injury_status


def player_state(raw: Mapping[str, Any]) -> PlayerState:
    return PlayerState(
        status=_text(raw.get("status")),
        injury_status=_text(raw.get("injury_status")),
        body_part=_text(raw.get("injury_body_part")),
        practice=_text(raw.get("practice_participation")),
        practice_desc=_text(raw.get("practice_description")),
        team=_text(raw.get("team")).upper(),
        position=_text(raw.get("position")).upper(),
    )


def is_tracked(raw: Any) -> bool:
    if not isinstance(raw, Mapping):
        return False
    return bool(_text(raw.get("team"))) and _text(raw.get("position")).upper() in TRACKED_POSITIONS


def tracked_states(players: Mapping[str, Any]) -> dict[str, PlayerState]:
    return {str(pid): player_state(raw) for pid, raw in players.items() if is_tracked(raw)}


# --------------------------------------------------------------------- changes
def _row(captured_at: str, season: int | None, week: int | None, pid: str, st: PlayerState, source: str) -> dict[str, Any]:
    return {
        "captured_at": captured_at,
        "season": "" if season is None else season,
        "week": "" if not week else week,
        "player_id": pid,
        "team": st.team,
        "position": st.position,
        "status": st.status,
        "injury_status": st.injury_status,
        "body_part": st.body_part,
        "practice": st.practice,
        "practice_desc": st.practice_desc,
        "source": source,
    }


def detect_changes(
    previous: Mapping[str, tuple[str, str, str, str]],
    players: Mapping[str, Any],
    *,
    captured_at: str,
    season: int | None,
    week: int | None,
) -> list[dict[str, Any]]:
    """Event rows for every tracked player whose state key differs from the last
    recorded one. ``previous`` is pid -> last recorded state key.

    * No prior record and healthy -> nothing (silence means healthy).
    * No prior record and not healthy -> a baseline event.
    * A recovery (healthy now, prior non-healthy) is recorded.
    """

    events: list[dict[str, Any]] = []
    for pid, st in sorted(tracked_states(players).items()):
        prior = previous.get(pid)
        key = st.key()
        if prior is None:
            if st.healthy:
                continue
        elif tuple(prior) == key:
            continue
        events.append(_row(captured_at, season, week, pid, st, SOURCE_LIVE))
    return events


def snapshot_rows(
    players: Mapping[str, Any], *, snapshot_key: str, captured_at: str, season: int | None, week: int | None
) -> tuple[list[dict[str, Any]], int]:
    """(non-healthy tracked rows, total tracked players)."""

    states = tracked_states(players)
    rows = []
    for pid, st in sorted(states.items()):
        if st.healthy:
            continue
        row = _row(captured_at, season, week, pid, st, SOURCE_SNAPSHOT)
        rows.append({"snapshot_key": snapshot_key, **row})
    return rows, len(states)


# ------------------------------------------------------------------- scheduling
def due_snapshot_key(now: datetime, taken_keys: Iterable[str]) -> str | None:
    """Key (``YYYY-MM-DD-slot``) of the most recent snapshot slot that has
    passed within the catch-up window and is not yet in ``taken_keys``."""

    now = now.astimezone(timezone.utc)
    taken = set(taken_keys)
    best: tuple[datetime, str] | None = None
    for day_back in range(0, 8):
        day = (now - timedelta(days=day_back)).date()
        for weekday, hour, name in SNAPSHOT_SLOTS:
            if day.weekday() != weekday:
                continue
            slot_time = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
            if slot_time > now or now - slot_time > SNAPSHOT_CATCHUP:
                continue
            if best is None or slot_time > best[0]:
                best = (slot_time, f"{day.isoformat()}-{name}")
    if best is None or best[1] in taken:
        return None
    return best[1]


def in_snapshot_season(now: datetime) -> bool:
    """Sep-Jan only (regular season + playoffs); off-season snapshots would be
    all-IR noise."""

    return now.astimezone(timezone.utc).month in (9, 10, 11, 12, 1)


# ------------------------------------------------------------------------- CSV
def rows_to_csv(rows: Sequence[Mapping[str, Any]], columns: Sequence[str], *, header: bool) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n", extrasaction="ignore")
    if header:
        writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    return buffer.getvalue()


def append_rows(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(rows_to_csv(rows, columns, header=new_file))


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def last_state_keys(event_rows: Iterable[Mapping[str, str]]) -> dict[str, tuple[str, str, str, str]]:
    """pid -> last recorded state key (rows are append-ordered)."""

    out: dict[str, tuple[str, str, str, str]] = {}
    for row in event_rows:
        pid = _text(row.get("player_id"))
        if pid:
            out[pid] = (
                _text(row.get("status")), _text(row.get("injury_status")),
                _text(row.get("body_part")), _text(row.get("practice")),
            )
    return out


def events_path(root: Path, season: int) -> Path:
    return root / HISTORY_DIR / f"events_{season}.csv"


def snapshots_path(root: Path, season: int) -> Path:
    return root / HISTORY_DIR / f"snapshots_{season}.csv"


def index_path(root: Path) -> Path:
    return root / HISTORY_DIR / "snapshot_index.csv"


def history_paths(root: Path, season: int) -> list[Path]:
    """Every file ``capture`` may create or modify for ``season``."""

    return [events_path(root, season), snapshots_path(root, season), index_path(root)]


# ----------------------------------------------------------------------- driver
def disabled(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return str(env.get(DISABLE_ENV, "")).strip().lower() in {"1", "true", "yes", "on"}


def capture(
    players: Mapping[str, Any],
    root: Path,
    *,
    now: datetime,
    season: int,
    week: int | None,
    dry_run: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Record change events (always) and a snapshot (when a slot is due).

    Returns a stats dict; never raises. With ``dry_run`` nothing is written.
    """

    stats: dict[str, Any] = {
        "enabled": not disabled(environ), "events": 0, "snapshot_key": None,
        "snapshot_rows": 0, "skipped": "", "dry_run": dry_run,
    }
    if disabled(environ):
        stats["skipped"] = "disabled"
        return stats
    try:
        if not isinstance(players, Mapping) or len(players) < MIN_PLAYERS_IN_DUMP:
            stats["skipped"] = "player dump too small to trust"
            return stats
        captured_at = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        ev_path = events_path(root, season)
        previous = last_state_keys(read_rows(events_path(root, season - 1)))
        previous.update(last_state_keys(read_rows(ev_path)))
        first_run = not previous
        events = detect_changes(previous, players, captured_at=captured_at, season=season, week=week)
        limit = MAX_EVENTS_FIRST_RUN if first_run else MAX_EVENTS_PER_RUN
        if len(events) > limit:
            stats["skipped"] = f"{len(events)} events exceeds sanity limit {limit}; not recorded"
            return stats
        stats["events"] = len(events)
        if not dry_run:
            append_rows(ev_path, events, EVENT_COLUMNS)

        idx = read_rows(index_path(root))
        key = due_snapshot_key(now, (r.get("snapshot_key", "") for r in idx)) if in_snapshot_season(now) else None
        if key:
            rows, total = snapshot_rows(players, snapshot_key=key, captured_at=captured_at, season=season, week=week)
            stats["snapshot_key"] = key
            stats["snapshot_rows"] = len(rows)
            if not dry_run:
                append_rows(snapshots_path(root, season), rows, SNAPSHOT_COLUMNS)
                append_rows(
                    index_path(root),
                    [{
                        "snapshot_key": key, "captured_at": captured_at, "season": season,
                        "week": "" if not week else week, "tracked_players": total, "rows": len(rows),
                    }],
                    INDEX_COLUMNS,
                )
    except Exception as exc:  # noqa: BLE001 - history must never break the sync
        stats["skipped"] = f"error: {type(exc).__name__}: {exc}"
    return stats
