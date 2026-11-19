"""Golden: moving the hardcoded age cutoffs into ``modules/age_profile.py`` must not change any output.

The fixture was captured on the pre-refactor code (``tests/age_cutoff_golden_support.py``). Never regenerate it to get
green: a behaviour change needs its own flag and its own new golden.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests import age_cutoff_golden_support as support

FIXTURE = Path(__file__).parent / "fixtures" / "age_cutoff_golden.json"
GOLDEN = json.loads(FIXTURE.read_text(encoding="utf-8"))
SNAPSHOT = {}


def _snap():
    if not SNAPSHOT:
        SNAPSHOT.update(support.snapshot())
    return SNAPSHOT


@pytest.mark.parametrize("group", sorted(GOLDEN))
def test_age_cutoff_golden(group):
    got = _snap()[group]
    for key, want in GOLDEN[group].items():
        assert got[key] == want, f"{group}.{key} changed"
