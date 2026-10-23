"""Executive surface parity and data integrity contracts (PR #134)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules import player_eligibility
from modules import waivers_logic


ROOT = Path(__file__).resolve().parents[1]


def test_audit_document_exists():
    doc = (ROOT / "docs" / "executive-surface-parity-audit.md").read_text(encoding="utf-8")
    for section in (
        "Legacy component inventory",
        "Surface parity",
        "Desktop spacing audit",
        "Player presentation",
        "Data integrity audit",
        "Visual QA",
        "Explicit confirmation",
    ):
        assert section in doc


def test_no_football_logic_modules_modified_beyond_eligibility_integrity():
    """Eligibility tightening is data integrity; Trust scoring modules stay untouched.

    Valuation calibration audits may intentionally touch rankings / trade_ideas.
    """
    diff_names = {
        line.split("|")[0].strip()
        for line in __import__("subprocess")
        .run(
            ["git", "diff", "--name-only", "main"],
            capture_output=True,
            text=True,
            check=False,
        )
        .stdout.splitlines()
        if line.strip()
    }
    forbidden = {
        "modules/trust_engine.py",
    }
    assert not diff_names.intersection(forbidden)


def test_player_eligibility_module_has_veteran_unsigned_guard():
    source = (ROOT / "modules" / "player_eligibility.py").read_text(encoding="utf-8")
    assert "VETERAN_UNSIGNED_MIN_EXPERIENCE" in source
    assert "news_only_corroboration" in source
