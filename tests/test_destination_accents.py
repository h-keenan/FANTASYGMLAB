"""One destination accent map for web nav/orb/catalog and the app."""

import subprocess
import sys
from pathlib import Path

from modules import destination_accents

ROOT = Path(__file__).resolve().parent.parent


def test_every_accent_is_a_known_semantic_token():
    assert set(destination_accents.ACCENT_BY_DESTINATION.values()) <= set(destination_accents.TOKENS)


def test_generated_ts_matches_python():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_destination_accents.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + "\nRun: python scripts/sync_destination_accents.py"
