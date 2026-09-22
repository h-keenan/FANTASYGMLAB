"""Repository root hygiene and generated-artifact contract."""

from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_ROOT_FILES = {
    ".gitignore",
    ".python-version",
    "AGENTS.md",
    "DEPENDENCIES.md",
    "DEPLOYMENT.md",
    "app.py",
    "favicon.ico",
    "favicon.png",
    "render.yaml",
    "requirements-dev.txt",
    "requirements.txt",
    "run_dynastygm_3030.bat",
}

ALLOWED_ROOT_DIRS = {
    ".git",
    ".github",
    ".streamlit",
    "artifacts",
    "assets",
    "config",
    "data",
    "docs",
    "modules",
    "scripts",
    "services",
    "tests",
}


def _tracked_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def test_no_tracked_root_tmp_or_streamlit_logs():
    tracked = _tracked_files()
    offenders = [
        path
        for path in tracked
        if "/" not in path
        and (
            path.startswith(".tmp_")
            or path.endswith(".out")
            or path.endswith(".err")
            or path.endswith(".log")
        )
    ]
    assert offenders == []


def test_root_tracked_files_are_intentional():
    tracked_root = [path for path in _tracked_files() if "/" not in path]
    unexpected = sorted(set(tracked_root) - ALLOWED_ROOT_FILES)
    assert unexpected == [], unexpected


def test_artifacts_are_not_tracked_except_gitkeep():
    tracked = [path for path in _tracked_files() if path.startswith("artifacts/")]
    assert tracked == ["artifacts/.gitkeep"]


def test_archetype_golden_fixture_lives_under_tests_fixtures():
    path = (
        ROOT
        / "tests"
        / "fixtures"
        / "archetype_experiments"
        / "contender_fixture_validation.json"
    )
    assert path.is_file()
    assert not (
        ROOT / "artifacts" / "archetype_experiments" / "contender_fixture_validation.json"
    ).exists()


def test_gitignore_covers_generated_families():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for needle in (
        "artifacts/**",
        ".tmp_streamlit_*",
        "data/launch_analytics.jsonl",
        "data/*.public-player-snapshot.pkl",
        ".cursor/",
        "data/*measurement*.json",
    ):
        assert needle in ignore


def test_contract_doc_exists():
    doc = (ROOT / "docs" / "repository-root-and-generated-artifact-contract.md").read_text(
        encoding="utf-8"
    )
    assert "Root inventory — before" in doc
    assert "players.db" in doc
    assert "artifacts/measurements/" in doc


def test_measure_app_wide_defaults_to_artifacts_measurements():
    source = (ROOT / "scripts" / "measure_app_wide_performance.py").read_text(
        encoding="utf-8"
    )
    assert 'ROOT / "artifacts" / "measurements" / "app_wide_performance.json"' in source
