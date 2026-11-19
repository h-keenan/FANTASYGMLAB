"""Golden: every posture-keyed number and every surface that reads one, pinned before the shared-model refactor.

Captured from the forked per-module tables (trade_grade, trade_posture, trade_hub_engine, trade_ideas,
multi_team_trade_finder, drop_candidates) and checked after they were folded into ``modules/posture_model.py``. The
refactor must not move a digit. Never regenerate this file to get green; a diff is a bug in the change under test.

Coverage: all 5 postures x 1QB / Superflex / TEP x 10 / 12 / 14 teams, with the starter-weight floor flag ON (default)
and OFF (subprocess, because the floor is read at import).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


from tests import posture_golden_support as S

GOLDEN = Path(__file__).parent / "fixtures" / "posture_golden.json"
ROOT = Path(__file__).resolve().parent.parent


def _want():
    return json.loads(GOLDEN.read_text())


def _floor_off_snapshot():
    env = {**os.environ, "DYNASTYGM_STARTER_WEIGHT_FLOOR_V1": "0", "DYNASTYGM_POSTURE_COHERENCE_V1": "0"}
    out = subprocess.run(
        [sys.executable, "-m", "tests.posture_golden_support"], cwd=ROOT, env={**env, "PYTHONPATH": str(ROOT)},
        capture_output=True, text=True, check=True,
    ).stdout
    line = next(x for x in out.splitlines() if x.startswith("GOLDEN_JSON="))
    return json.loads(line[len("GOLDEN_JSON="):])


def _legacy_snapshot():
    """Pre-coherence goldens: the coherence flag defaults ON, so they are checked with it switched OFF (subprocess)."""
    env = {**os.environ, "DYNASTYGM_POSTURE_COHERENCE_V1": "0", "POSTURE_GOLDEN_MODE": "legacy"}
    out = subprocess.run(
        [sys.executable, "-m", "tests.posture_golden_support"], cwd=ROOT, env={**env, "PYTHONPATH": str(ROOT)},
        capture_output=True, text=True, check=True,
    ).stdout
    line = next(x for x in out.splitlines() if x.startswith("GOLDEN_JSON="))
    return json.loads(line[len("GOLDEN_JSON="):])


def _compare(got, want, label):
    assert got.keys() == want.keys(), label
    for key in want:
        assert got[key] == want[key], f"{label}: {key}"


def test_posture_tables_and_age_curves_are_unchanged():
    _compare(_legacy_snapshot()["tables"], _want()["tables_on"], "tables (floor on, coherence off)")


def test_trade_grade_verdicts_are_unchanged_for_every_posture_and_format():
    _compare(_legacy_snapshot()["grade"], _want()["grade_on"], "grade (floor on, coherence off)")


def test_floor_off_tables_and_grades_are_unchanged():
    got = _floor_off_snapshot()
    _compare(got["tables"], _want()["tables_off"], "tables (floor off)")
    _compare(got["grade"], _want()["grade_off"], "grade (floor off)")


def test_hub_finder_and_gm_plan_are_unchanged():
    _compare(_legacy_snapshot()["engine"], _want()["engine"], "hub/finder/gm plan (coherence off)")


def test_three_team_finder_is_unchanged():
    _compare(_legacy_snapshot()["multi"], _want()["multi"], "multi-team finder (coherence off)")


COHERENCE_GOLDEN = Path(__file__).parent / "fixtures" / "posture_golden_coherence.json"


def _coherence_snapshot():
    env = {**os.environ, "DYNASTYGM_POSTURE_COHERENCE_V1": "1", "POSTURE_GOLDEN_MODE": "coherence"}
    out = subprocess.run(
        [sys.executable, "-m", "tests.posture_golden_support"], cwd=ROOT, env={**env, "PYTHONPATH": str(ROOT)},
        capture_output=True, text=True, check=True,
    ).stdout
    line = next(x for x in out.splitlines() if x.startswith("GOLDEN_JSON="))
    return json.loads(line[len("GOLDEN_JSON="):])


def test_coherence_flag_on_matches_its_own_golden():
    """DYNASTYGM_POSTURE_COHERENCE_V1=1 (default ON since 2026-11-19): every table, grade, Hub/Finder/GM Plan and 3-team result."""

    got, want = _coherence_snapshot(), json.loads(COHERENCE_GOLDEN.read_text())
    _compare(got, want, "coherence on")


def test_coherence_flag_on_is_the_default(monkeypatch):
    from modules import posture_model

    monkeypatch.delenv(posture_model.COHERENCE_ENV_KEY, raising=False)
    assert posture_model.coherence_enabled() is True
    monkeypatch.setenv(posture_model.COHERENCE_ENV_KEY, "0")
    assert posture_model.coherence_enabled() is False


if __name__ == "__main__" and os.environ.get("POSTURE_GOLDEN_CAPTURE_COHERENCE"):  # pragma: no cover - capture helper
    COHERENCE_GOLDEN.write_text(json.dumps(_coherence_snapshot(), sort_keys=True, indent=0))

if __name__ == "__main__" and os.environ.get("POSTURE_GOLDEN_CAPTURE"):  # pragma: no cover - capture helper
    snap = {
        "tables_on": S.tables_snapshot(), "grade_on": S.grade_snapshot(),
        "engine": S.engine_snapshot(), "multi": S.multi_team_snapshot(),
    }
    off = _floor_off_snapshot()
    snap["tables_off"], snap["grade_off"] = off["tables"], off["grade"]
    GOLDEN.write_text(json.dumps(snap, sort_keys=True, indent=0))
