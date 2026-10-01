"""Cron entrypoint: refresh data/players.db and push the result to main.

Run by Render's fantasygm-lab-players-db-refresh cron job (see render.yaml)
on a schedule. This is the fix for the P0 incident where data/players.db sat
~11 weeks stale in production with no scheduled refresh anywhere.

Why "commit to git and push", not a shared disk
-------------------------------------------------
data/players.db needs to reach two independently-deployed, always-on Render
web services (fantasygm-lab's Streamlit app and fantasygm-lab-mobile-api's
FastAPI app), both of which read it via a plain relative path
("data/players.db") baked into their own git checkout. Render persistent
disks are attached to exactly one service and are not reachable from any
other service or from a job/cron run at all
(https://render.com/docs/disks: "A persistent disk is accessible by only a
single service instance ... You can't access a service's disk from any
other service" / "Disks aren't available ... for one-off jobs"). Neither
fantasygm-lab nor fantasygm-lab-mobile-api has a `disk:` block today, and a
disk shared between them (or between either and this cron) is not something
Render supports. So there is no way for this cron to refresh a single file
that both running services can see at runtime -- the only mechanism that
reaches every service's own checkout is a new commit on the branch they
already auto-deploy from (`autoDeploy: true`, `branch: main` on both).
Rebuilding players.db here and pushing it to main lets Render's existing
auto-deploy machinery do the "get it to every service" part for free.

Safety contract
----------------
This script commits/pushes ONLY when all of the following hold:
1. The refresh subprocess (scripts/refresh_players_db_subprocess.py, which
   wraps modules.rankings.build_players_table(db_path, refresh=True)) exits
   0. That function only writes to db_path after it has successfully built
   a complete, non-empty DataFrame -- any failure midway (bad Sleeper
   response, empty frame, exception) leaves the previous players.db file
   completely untouched and the subprocess exits non-zero. See that
   script's own module docstring.
2. After a 0 exit, players.db still exists on disk and is non-empty --
   a second, independent guard against a "successful" run that
   nonetheless produced nothing (belt-and-suspenders on top of (1)).
3. The file's content (or a tracked sibling cache file's content -- see
   SIBLING_CACHE_PATHS) actually changed versus what is already committed.
   A run that fetches the same data as last time is a deliberate no-op:
   no empty/no-diff commit is ever created.

Only files that changed are staged and committed; anything unrelated in the
working tree is left alone.

IMPORTANT (this task's safety rule): this script is the production
automation meant to refresh the real data/players.db on a schedule when run
by the actual cron job. It must never be invoked against the real repo
checkout for local testing/dry-runs -- see tests/test_refresh_and_commit_players_db.py,
which exercises refresh_and_commit() against throwaway git repos under
pytest's tmp_path, never this repository's own working tree.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DB_PATH = ROOT / "data" / "players.db"
# Sibling cache files that a refresh=True build_players_table run may also
# rewrite as a side effect (modules.sleeper.get_players writes
# sleeper_players.json; modules.fantasycalc.get_dynasty_values writes
# fantasycalc_values.csv on its own separate 6h TTL). Only ones that
# actually changed get included in the commit.
DEFAULT_SIBLING_PATHS: tuple[Path, ...] = (
    ROOT / "data" / "sleeper_players.json",
    ROOT / "data" / "fantasycalc_values.csv",
)
REFRESH_SUBPROCESS_SCRIPT = ROOT / "scripts" / "refresh_players_db_subprocess.py"
REFRESH_SUBPROCESS_TIMEOUT_S = 600

GIT_BRANCH = "main"
COMMIT_AUTHOR_NAME = "FantasyGM Lab Players DB Bot"
COMMIT_AUTHOR_EMAIL = "players-db-bot@users.noreply.github.com"
COMMIT_MESSAGE_SUBJECT = "chore(data): scheduled players.db refresh"

DEFAULT_REPO_SLUG = "h-keenan/FANTASYGMLAB"


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_refresh_runner(db_path: Path) -> int:
    """Invoke the existing (already safety-checked) refresh subprocess.

    Returns its exit code: 0 means a genuinely successful, non-empty build
    (see scripts/refresh_players_db_subprocess.py); anything else means the
    previous players.db was left untouched.
    """

    try:
        completed = subprocess.run(
            [sys.executable, str(REFRESH_SUBPROCESS_SCRIPT), str(db_path)],
            cwd=str(ROOT),
            timeout=REFRESH_SUBPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        print("refresh subprocess timed out", file=sys.stderr)
        return 1
    return completed.returncode


def _run_git(
    repo_root: Path, args: Sequence[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def sync_to_latest_branch(repo_root: Path, remote: str, branch: str) -> bool:
    """Best-effort: make the local checkout match <remote>/<branch>.

    A cron container's checkout may be older than main by the time it
    actually fires. Fetching + hard-resetting here means the before/after
    diff below is computed against genuinely current committed data, and
    that this script's own push is a fast-forward instead of rejected.
    """

    fetch = _run_git(repo_root, ["fetch", remote, branch])
    if fetch.returncode != 0:
        print(f"git fetch failed: {fetch.stderr.strip()}", file=sys.stderr)
        return False
    reset = _run_git(repo_root, ["reset", "--hard", "FETCH_HEAD"])
    if reset.returncode != 0:
        print(f"git reset failed: {reset.stderr.strip()}", file=sys.stderr)
        return False
    return True


def refresh_and_commit(
    *,
    repo_root: Path,
    db_path: Path,
    sibling_paths: Sequence[Path] = (),
    push_url: str | None,
    refresh_runner: Callable[[Path], int] = default_refresh_runner,
    sync_first: bool = True,
    sync_remote: str = "origin",
    branch: str = GIT_BRANCH,
    commit_author_name: str = COMMIT_AUTHOR_NAME,
    commit_author_email: str = COMMIT_AUTHOR_EMAIL,
    commit_message_subject: str = COMMIT_MESSAGE_SUBJECT,
    commit_message_note: str = "Automated by the fantasygm-lab-players-db-refresh cron.",
) -> int:
    """Refresh db_path in place, then commit+push only a genuine, changed,
    successful result.

    The commit_author_*/commit_message_* parameters default to this
    script's own identity/message so existing callers (and the Render cron
    that runs this file directly) are unaffected. Other scripts that reuse
    this same commit/push plumbing for a different kind of players.db write
    (e.g. scripts/sync_injury_status.py's narrow column patch, as opposed to
    a full rebuild) pass their own values so the git history and bot
    identity accurately reflect which automation made the change.

    Returns a process-style exit code: 0 for either a real push or a
    legitimate no-op (nothing changed); 1 for any failure (refresh failed,
    refresh produced an empty file, sync failed, git commands failed, or no
    push_url is configured).
    """

    if sync_first and not sync_to_latest_branch(repo_root, sync_remote, branch):
        print(
            "could not sync checkout to latest branch; aborting without touching players.db",
            file=sys.stderr,
        )
        return 1

    candidate_paths = [db_path, *sibling_paths]
    before_hashes = {path: _sha256(path) for path in candidate_paths}

    print(f"running players.db refresh against {db_path} ...")
    exit_code = refresh_runner(db_path)
    if exit_code != 0:
        print(
            f"refresh failed (exit {exit_code}); leaving players.db untouched",
            file=sys.stderr,
        )
        return 1

    if not db_path.exists() or db_path.stat().st_size == 0:
        print(
            "refresh reported success but players.db is missing/empty; refusing to commit",
            file=sys.stderr,
        )
        return 1

    after_hashes = {path: _sha256(path) for path in candidate_paths}
    changed = [
        path
        for path in candidate_paths
        if after_hashes[path] is not None and after_hashes[path] != before_hashes[path]
    ]

    if not changed:
        print("refresh produced no content changes; nothing to commit")
        return 0

    rel_paths = [str(path.relative_to(repo_root)) for path in changed]
    print(f"changed files: {rel_paths}")

    add = _run_git(repo_root, ["add", *rel_paths])
    if add.returncode != 0:
        print(f"git add failed: {add.stderr.strip()}", file=sys.stderr)
        return 1

    # Belt-and-suspenders: our own hash comparison already gates this, but
    # confirm git agrees something is actually staged before committing.
    diff_check = _run_git(repo_root, ["diff", "--cached", "--quiet"])
    if diff_check.returncode == 0:
        print("git reports no staged changes after add; nothing to commit")
        return 0

    commit_env = dict(os.environ)
    commit_env["GIT_AUTHOR_NAME"] = commit_author_name
    commit_env["GIT_AUTHOR_EMAIL"] = commit_author_email
    commit_env["GIT_COMMITTER_NAME"] = commit_author_name
    commit_env["GIT_COMMITTER_EMAIL"] = commit_author_email
    message = (
        f"{commit_message_subject}\n\n"
        f"{commit_message_note}\n"
        f"Files: {', '.join(rel_paths)}"
    )
    commit = _run_git(repo_root, ["commit", "-m", message], env=commit_env)
    if commit.returncode != 0:
        print(f"git commit failed: {commit.stderr.strip()}", file=sys.stderr)
        return 1

    if not push_url:
        print(
            "no push URL configured (GITHUB_PUSH_TOKEN missing); committed "
            "locally but cannot push",
            file=sys.stderr,
        )
        return 1

    push = _run_git(repo_root, ["push", push_url, f"HEAD:{branch}"])
    if push.returncode != 0:
        print(f"git push failed: {push.stderr.strip()}", file=sys.stderr)
        return 1

    print("pushed players.db refresh")
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
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
