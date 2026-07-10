from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import app_config

REQUIRED_FILES = (
    ".python-version",
    "render.yaml",
    "requirements.txt",
    "app.py",
    "modules/app_config.py",
    "config/secrets.example.toml",
    "config/README.md",
    "docs/RENDER_DEPLOYMENT.md",
    "docs/DEVELOPMENT_WORKFLOW.md",
    ".github/workflows/ci.yml",
)
REQUIRED_REQUIREMENTS = ("streamlit", "pandas", "requests", "stripe")
IGNORED_SCAN_DIRS = {".git", "venv", ".venv", "__pycache__", ".pytest_cache", ".streamlit", "local_secrets"}
IGNORED_SCAN_SUFFIXES = (".pyc", ".log", ".out", ".err")
SECRET_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]{12,}"),
    re.compile(r"rk_live_[A-Za-z0-9]{12,}"),
    re.compile(r"whsec_[A-Za-z0-9]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
)


def _fail(message: str) -> None:
    raise SystemExit(f"deployment check failed: {message}")


def _repo_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith(".tmp_") or path.suffix in IGNORED_SCAN_SUFFIXES:
            continue
        rel_parts = set(path.relative_to(ROOT).parts)
        if rel_parts & IGNORED_SCAN_DIRS:
            continue
        files.append(path)
    return files


def check_python_version() -> None:
    if sys.version_info < (3, 12) or sys.version_info >= (3, 13):
        _fail(f"Python 3.12 is required, got {sys.version.split()[0]}")


def check_required_files() -> None:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).exists()]
    if missing:
        _fail("missing required files: " + ", ".join(missing))
    pinned = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    if pinned != "3.12.10":
        _fail(".python-version must pin 3.12.10")


def check_requirements() -> None:
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8").casefold()
    missing = [package for package in REQUIRED_REQUIREMENTS if package not in text]
    if missing:
        _fail("requirements.txt missing: " + ", ".join(missing))


def check_secret_patterns() -> None:
    offenders: list[str] = []
    for path in _repo_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(str(path.relative_to(ROOT)))
                break
    if offenders:
        _fail("possible committed secret pattern in: " + ", ".join(sorted(offenders)))


def check_base_url() -> None:
    base_url = app_config.app_base_url()
    configured = os.environ.get("APP_BASE_URL", "").strip()
    if configured and not configured.startswith("https://"):
        _fail("APP_BASE_URL must use HTTPS outside local development")
    if "duckdns" in base_url.casefold() or "streamlit.app" in base_url.casefold():
        _fail("APP_BASE_URL points at an obsolete host")


def check_import() -> None:
    importlib.import_module("app")


def main() -> int:
    check_python_version()
    check_required_files()
    check_requirements()
    check_secret_patterns()
    check_base_url()
    check_import()
    print("deployment check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
