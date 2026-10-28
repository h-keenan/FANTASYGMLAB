"""Audit C5: one injury tone map for server badges, web and the app."""

import subprocess
import sys
from pathlib import Path

from modules import football_assets, injury_tone

ROOT = Path(__file__).resolve().parent.parent


def test_golden_rows():
    for status, tone in injury_tone.GOLDEN:
        assert injury_tone.injury_tone(status) == tone, status


def test_doubtful_and_questionable_never_share_a_tone():
    assert injury_tone.injury_tone("Doubtful") == "danger"
    assert injury_tone.injury_tone("Questionable") == "warning"


def test_server_badge_reads_the_same_map():
    for status, tone in injury_tone.GOLDEN:
        if not status.strip():
            continue
        css = {"warning": "caution"}.get(tone, tone)
        assert f"dg-football-injury--{css}" in football_assets.injury_badge_html(status), status


def test_generated_ts_matches_python():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_injury_tone.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + "\nRun: python scripts/sync_injury_tone.py"
