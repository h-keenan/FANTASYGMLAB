"""Cron entrypoint: patch ONLY injury-related columns in data/players.db from
Sleeper's live player feed, much more often than the full players.db rebuild.

Why this exists (separate from fantasygm-lab-players-db-refresh)
------------------------------------------------------------------
scripts/refresh_and_commit_players_db.py / build_players_table() already
rebuild the whole of data/players.db -- including status/injury_status --
every 6 hours. That cadence is fine for the dozens of other columns it also
recomputes (valuation, scoring, usage shares, stats joins, ...), but it is
too coarse specifically for injury status: a player ruled OUT on a Friday
afternoon, or upgraded from Questionable to Doubtful, can sit stale in
players.db for most of a game week until the next 6-hour tick fires.
modules.sleeper.get_players() already fetches Sleeper's full raw player
list -- status/injury_status included -- cheaply (no valuation recompute,
its own 5-minute disk cache), so this script does the minimum possible work
to keep just those columns fresh: fetch the list, and UPDATE two columns
per matching player_id row directly in the existing SQLite file. It never
runs build_players_table() and never touches any valuation/score/usage
column.

What gets patched
------------------
Exactly two columns, both already present in the "players" table and both
sourced from Sleeper the same way modules.rankings.normalize_player_record
does it during a full rebuild (reused here via that same function, so there
is only one place that maps Sleeper's raw fields -> these two columns):

  - status          (Sleeper's roster status, e.g. "Active", "Injured
                      Reserve"; raw/un-lowercased, matching normalize_
                      player_record's "status" field)
  - injury_status    (Sleeper's weekly injury designation, e.g.
                      "Questionable"/"Doubtful"/"Out"; normalize_player_
                      record also folds Sleeper's injury_notes into this
                      same field when injury_status itself is blank)

PLAYER_COLUMNS in modules/rankings.py has no other raw-Sleeper injury
sibling field actually persisted to the table -- injury_level,
injury_risk_score and injury_multiplier are *derived* valuation-adjacent
columns computed by apply_valuation_model() during a full rebuild, and are
deliberately left untouched here; recomputing them correctly needs the full
roster/depth-chart context a narrow patch does not have.

New players Sleeper knows about but players.db does not
-----------------------------------------------------------
Skipped, on purpose. A row in players.db needs every other PLAYER_COLUMNS
value (name, position, value, score, stats joins, eligibility, ...) to be
usable by the app; inserting a minimal placeholder row with only
status/injury_status populated (and everything else NULL/empty) would make
that row behave unpredictably everywhere else in the app that assumes a
fully-populated players.db row. The next full rebuild (at most 6 hours
away) adds genuinely new players with all of those columns computed
together, which is the only place that should ever INSERT a new player row.

Safety contract
----------------
Same discipline as scripts/refresh_and_commit_players_db.py, whose
commit/push helper (refresh_and_commit) this script imports and reuses
rather than reimplementing: commits/pushes only when
  1. The Sleeper fetch actually returned data (never on an empty/failed
     response -- modules.sleeper.get_players() returns {} on any fetch
     failure and never raises, so an empty dict is the correct "nothing to
     do, don't commit" signal).
  2. players.db still exists and is non-empty afterward.
  3. The file's content (or the tracked sleeper_players.json cache sibling
     -- see SIBLING_PATHS) actually changed vs. what is already committed.
A run that finds no injury-status changes is a deliberate no-op: no
empty/no-diff commit is ever created.

Coexisting with the 6-hour full rebuild without racing
---------------------------------------------------------
Both crons call sync_to_latest_branch() (fetch + hard-reset to origin/main)
before computing their own before/after diff, and neither ever force-pushes
-- see refresh_and_commit()'s plain `git push push_url HEAD:branch`. If both
happen to run close together:
  - Each starts from a fresh, independently-synced checkout and computes
    its own local commit on top of the same parent.
  - Whichever pushes first wins a normal git fast-forward.
  - The second push is a non-fast-forward and is rejected outright (no
    --force anywhere in either script), so it can never clobber the
    winner's commit -- it simply fails that run (exit 1) and the local
    commit evaporates with the ephemeral cron container.
  - The "losing" run's update is not lost forever: the next scheduled run
    of either cron starts with sync_to_latest_branch() against the new
    HEAD and recomputes a fresh diff, so a dropped injury-status change is
    retried within <=30 minutes (this cron's own cadence), and a dropped
    full-rebuild change within <=6 hours. In the specific case where the
    full rebuild's push wins, its own Sleeper fetch happened in essentially
    the same real-world window, so the injury-sync's dropped write would
    have been redundant with what the rebuild already wrote anyway.
This is the same "last fast-forward wins, no data loss, retried next cycle"
property a normal distributed git workflow already has with a single
writer cron; adding a second, more frequent writer does not introduce a new
failure mode, only a (harmless) higher chance of a single run's push being
rejected and retried.

IMPORTANT (this task's safety rule): this script is production automation
meant to patch the real data/players.db on a schedule when run by the
actual cron job. It must never be invoked against the real repo checkout
for local testing/dry-runs -- see tests/test_sync_injury_status.py, which
exercises patch_injury_columns() against throwaway SQLite files under
pytest's tmp_path, never this repository's own data/players.db.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import sleeper  # noqa: E402
from modules.rankings import normalize_player_record  # noqa: E402
from scripts.refresh_and_commit_players_db import (  # noqa: E402
    DEFAULT_REPO_SLUG,
    refresh_and_commit,
)

DEFAULT_DB_PATH = ROOT / "data" / "players.db"
# modules.sleeper.get_players() rewrites this cache file on a live (cache
# miss) fetch; it is already a tracked sibling of players.db (see
# scripts/refresh_and_commit_players_db.py's DEFAULT_SIBLING_PATHS) and is
# read directly elsewhere (modules.sleeper.load_cached_players_disk) to
# patch status/injury/depth without a fresh fetch, so it is just as
# injury-relevant as players.db itself and gets the same commit treatment.
DEFAULT_SIBLING_PATHS: tuple[Path, ...] = (ROOT / "data" / "sleeper_players.json",)

TABLE_NAME = "players"
# The only two columns this script is allowed to write. Deliberately not
# including injury_level/injury_risk_score/injury_multiplier -- those are
# derived valuation outputs, not raw Sleeper fields, and recomputing them
# correctly requires the full roster context a narrow patch does not have.
INJURY_COLUMNS: tuple[str, ...] = ("status", "injury_status")

GIT_BRANCH = "main"
COMMIT_AUTHOR_NAME = "FantasyGM Lab Injury Sync Bot"
COMMIT_AUTHOR_EMAIL = "injury-sync-bot@users.noreply.github.com"
COMMIT_MESSAGE_SUBJECT = "chore(data): scheduled injury-status sync"
COMMIT_MESSAGE_NOTE = (
    "Automated by the fantasygm-lab-injury-status-sync cron. Patches only "
    "the status/injury_status columns of existing data/players.db rows "
    "from Sleeper's live player feed -- not a full players.db rebuild."
)


def patch_injury_columns(db_path: Path, players: Dict[str, Any]) -> Tuple[int, int]:
    """Patch status/injury_status in place for matching player_id rows.

    ``players`` is the raw dict returned by modules.sleeper.get_players()
    (player_id -> Sleeper's raw player object). Each value is normalized
    with modules.rankings.normalize_player_record -- the exact same
    function a full rebuild uses -- so there is a single source of truth
    for how Sleeper's raw fields map onto these two columns.

    Players present in ``players`` but absent from the local "players"
    table are skipped (see module docstring). Rows whose status and
    injury_status already match are left untouched (no-op write avoided).

    Returns (rows_in_local_db, rows_updated). Never raises for a missing
    db file/table -- callers treat that as "nothing to patch", matching
    get_players()'s own "never raise, return an empty/safe value" contract.
    """

    if not db_path.exists() or db_path.stat().st_size == 0:
        print(f"{db_path} is missing or empty; nothing to patch", file=sys.stderr)
        return (0, 0)

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE_NAME,),
        )
        if cur.fetchone() is None:
            print(f"{db_path} has no '{TABLE_NAME}' table; nothing to patch", file=sys.stderr)
            return (0, 0)

        cur.execute(f"SELECT player_id, status, injury_status FROM {TABLE_NAME}")
        existing = {
            str(row[0]): (row[1] or "", row[2] or "") for row in cur.fetchall()
        }

        updates = []
        for pid, raw in players.items():
            pid = str(pid)
            if pid not in existing:
                # New-to-Sleeper player not yet in players.db: skip, see
                # module docstring -- only a full rebuild inserts rows.
                continue
            if not isinstance(raw, dict):
                continue

            record = normalize_player_record(pid, raw)
            new_status = str(record.get("status") or "")
            new_injury_status = str(record.get("injury_status") or "")
            old_status, old_injury_status = existing[pid]

            if new_status == old_status and new_injury_status == old_injury_status:
                continue
            updates.append((new_status, new_injury_status, pid))

        if updates:
            cur.executemany(
                f"UPDATE {TABLE_NAME} SET status = ?, injury_status = ? WHERE player_id = ?",
                updates,
            )
            conn.commit()

        return (len(existing), len(updates))
    finally:
        conn.close()


def default_patch_runner(db_path: Path) -> int:
    """Fetch Sleeper's player list and patch db_path's injury columns.

    Returns 0 only on a genuinely successful (possibly no-op) patch; 1 on
    any fetch failure. get_players() never raises -- a bad response, retry
    exhaustion, or network error all surface as an empty dict, which is
    exactly what must NOT be allowed to reach refresh_and_commit() as a
    "success" (an empty Sleeper response must never wipe/zero out existing
    injury data).
    """

    # refresh=False: Sleeper's own 5-minute disk cache (modules.sleeper.
    # PLAYERS_CACHE_TTL_SECONDS) already comfortably covers this cron's own
    # 30-minute cadence, so a run that lands within 5 minutes of another
    # consumer's fetch (e.g. the full rebuild cron, or the live app) reuses
    # that fetch instead of hitting Sleeper again.
    players = sleeper.get_players(refresh=False)
    if not players:
        print(
            "modules.sleeper.get_players() returned no data; leaving "
            "players.db untouched",
            file=sys.stderr,
        )
        return 1

    examined, updated = patch_injury_columns(db_path, players)
    print(
        f"examined {examined} local players.db rows; "
        f"patched status/injury_status on {updated} of them"
    )
    return 0


def main(argv: list[str]) -> int:
    push_token = os.environ.get("GITHUB_PUSH_TOKEN", "").strip()
    repo_slug = os.environ.get("GITHUB_REPO_SLUG", DEFAULT_REPO_SLUG).strip()
    push_url = (
        f"https://x-access-token:{push_token}@github.com/{repo_slug}.git"
        if push_token
        else None
    )
    return refresh_and_commit(
        repo_root=ROOT,
        db_path=DEFAULT_DB_PATH,
        sibling_paths=DEFAULT_SIBLING_PATHS,
        push_url=push_url,
        refresh_runner=default_patch_runner,
        branch=GIT_BRANCH,
        commit_author_name=COMMIT_AUTHOR_NAME,
        commit_author_email=COMMIT_AUTHOR_EMAIL,
        commit_message_subject=COMMIT_MESSAGE_SUBJECT,
        commit_message_note=COMMIT_MESSAGE_NOTE,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
