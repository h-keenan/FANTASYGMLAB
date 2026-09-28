"""Tests for scripts/refresh_and_commit_players_db.py's commit/push gating.

Exercises refresh_and_commit() against real, throwaway local git repositories
created fresh under pytest's tmp_path for every test (a "work" checkout plus
a local bare "remote") -- never the real repository, never a real network
push, and never anything under this project's own data/ directory. This
follows the same safety rule the rest of the task operates under: never let
test/investigation code touch the real data/players.db.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "refresh_and_commit_players_db.py"
_spec = importlib.util.spec_from_file_location("refresh_and_commit_players_db", _MODULE_PATH)
rac = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(rac)


def _git(repo: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), check=True, capture_output=True, text=True, env=env
    )


def _log(repo: Path) -> str:
    return subprocess.run(
        ["git", "log", "--oneline", "--all"], cwd=str(repo), capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo_with_remote(tmp_path):
    """A local bare 'remote' plus a 'work' checkout with an initial commit
    containing data/players.db + data/sleeper_players.json, wired together
    like origin/main would be.
    """

    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)

    work = tmp_path / "work"
    work.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    _git(work, "remote", "add", "origin", str(remote))

    data_dir = work / "data"
    data_dir.mkdir()
    db_path = data_dir / "players.db"
    db_path.write_bytes(b"OLD-PLAYERS-DB-BYTES")
    sibling_path = data_dir / "sleeper_players.json"
    sibling_path.write_text('{"old": true}')
    (work / "README.md").write_text("placeholder\n")

    _git(work, "add", "-A")
    _git(work, "commit", "-m", "init")
    _git(work, "push", "origin", "main")

    return work, remote, db_path, sibling_path


def test_failed_refresh_does_not_commit_or_push(repo_with_remote):
    work, remote, db_path, sibling_path = repo_with_remote
    before_remote_log = _log(remote)

    def failing_runner(_db_path: Path) -> int:
        # Per the refresh subprocess's own contract, a failure must not
        # touch the file at all.
        return 1

    rc = rac.refresh_and_commit(
        repo_root=work,
        db_path=db_path,
        sibling_paths=[sibling_path],
        push_url=str(remote),
        refresh_runner=failing_runner,
    )

    assert rc == 1
    assert _log(remote) == before_remote_log
    assert db_path.read_bytes() == b"OLD-PLAYERS-DB-BYTES"


def test_success_reported_but_file_left_empty_does_not_commit(repo_with_remote):
    work, remote, db_path, sibling_path = repo_with_remote
    before_remote_log = _log(remote)

    def hollow_success_runner(target_db_path: Path) -> int:
        # Simulates a buggy/edge-case refresh that reports success (exit 0)
        # but leaves an empty file -- the extra size guard must catch this.
        target_db_path.write_bytes(b"")
        return 0

    rc = rac.refresh_and_commit(
        repo_root=work,
        db_path=db_path,
        sibling_paths=[sibling_path],
        push_url=str(remote),
        refresh_runner=hollow_success_runner,
    )

    assert rc == 1
    assert _log(remote) == before_remote_log


def test_successful_refresh_with_identical_content_is_a_noop(repo_with_remote):
    work, remote, db_path, sibling_path = repo_with_remote
    before_remote_log = _log(remote)

    def unchanged_runner(target_db_path: Path) -> int:
        target_db_path.write_bytes(b"OLD-PLAYERS-DB-BYTES")
        return 0

    rc = rac.refresh_and_commit(
        repo_root=work,
        db_path=db_path,
        sibling_paths=[sibling_path],
        push_url=str(remote),
        refresh_runner=unchanged_runner,
    )

    assert rc == 0
    assert _log(remote) == before_remote_log


def test_successful_changed_refresh_commits_and_pushes(repo_with_remote, tmp_path):
    work, remote, db_path, sibling_path = repo_with_remote

    def changed_runner(target_db_path: Path) -> int:
        target_db_path.write_bytes(b"NEW-PLAYERS-DB-BYTES")
        target_db_path.parent.joinpath("sleeper_players.json").write_text('{"new": true}')
        return 0

    rc = rac.refresh_and_commit(
        repo_root=work,
        db_path=db_path,
        sibling_paths=[sibling_path],
        push_url=str(remote),
        refresh_runner=changed_runner,
    )

    assert rc == 0
    log = _log(remote)
    assert "scheduled players.db refresh" in log

    check = tmp_path / "check_clone"
    subprocess.run(["git", "clone", str(remote), str(check)], check=True, capture_output=True)
    assert (check / "data" / "players.db").read_bytes() == b"NEW-PLAYERS-DB-BYTES"
    assert (check / "data" / "sleeper_players.json").read_text() == '{"new": true}'


def test_missing_push_url_commits_locally_but_reports_failure(repo_with_remote):
    work, remote, db_path, sibling_path = repo_with_remote
    before_remote_log = _log(remote)

    def changed_runner(target_db_path: Path) -> int:
        target_db_path.write_bytes(b"NEW-PLAYERS-DB-BYTES")
        return 0

    rc = rac.refresh_and_commit(
        repo_root=work,
        db_path=db_path,
        sibling_paths=[sibling_path],
        push_url=None,
        refresh_runner=changed_runner,
    )

    assert rc == 1
    # Nothing reached the remote even though a local commit exists.
    assert _log(remote) == before_remote_log
    local_log = _log(work)
    assert "scheduled players.db refresh" in local_log


def test_only_the_changed_sibling_files_are_staged(repo_with_remote):
    work, remote, db_path, sibling_path = repo_with_remote

    def only_db_changed_runner(target_db_path: Path) -> int:
        target_db_path.write_bytes(b"NEW-PLAYERS-DB-BYTES")
        # sibling_path deliberately left untouched.
        return 0

    rc = rac.refresh_and_commit(
        repo_root=work,
        db_path=db_path,
        sibling_paths=[sibling_path],
        push_url=str(remote),
        refresh_runner=only_db_changed_runner,
    )

    assert rc == 0
    show = subprocess.run(
        ["git", "show", "--stat", "--oneline", "HEAD"], cwd=str(work), capture_output=True, text=True
    ).stdout
    assert "players.db" in show
    assert "sleeper_players.json" not in show
