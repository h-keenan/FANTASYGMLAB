"""Guard: no posture weight table may be defined outside ``modules/posture_model.py``.

The audit (docs/audits/2026-11-band-aid-audit.md, item 1) found "how much does a rebuilder value now vs later" forked
across five modules, each tuned on its own scale; tuning one broke another. They now live in one module. This test
fails when a dict literal keyed by two or more posture names with NUMERIC values (a weight, multiplier, floor, or a
tuple of numbers) appears anywhere else under ``modules/`` or ``services/``, so a fork cannot quietly come back.

Dicts whose values are strings or posture names (display labels, posture -> posture maps) are not weights and are
fine. If you need a new posture-keyed number, add it to ``modules/posture_model.py`` and read it from there.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "modules" / "posture_model.py"
POSTURES = {"contender", "fringe_contender", "retool", "rebuild", "tank"}
# Fewer than this many posture keys is not a posture table (e.g. a one-off {"tank": ..., "other": ...} switch).
MIN_POSTURE_KEYS = 2


def _is_numeric(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_numeric(node.operand)
    if isinstance(node, (ast.Tuple, ast.List)):
        return bool(node.elts) and all(_is_numeric(e) for e in node.elts)
    return False


def _offences(path: Path, root: Path = ROOT) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keyed = [
            v for k, v in zip(node.keys, node.values)
            if isinstance(k, ast.Constant) and k.value in POSTURES
        ]
        if len(keyed) >= MIN_POSTURE_KEYS and all(_is_numeric(v) for v in keyed):
            found.append(f"{path.relative_to(root)}:{node.lineno}")
    return found


def _sources():
    for base in ("modules", "services"):
        for path in sorted((ROOT / base).rglob("*.py")):
            if path != MODEL:
                yield path


def test_no_posture_weight_tables_outside_posture_model():
    offences = [o for path in _sources() for o in _offences(path)]
    assert not offences, (
        "Posture-keyed numeric tables belong in modules/posture_model.py (one source, golden-tested as one unit): "
        + ", ".join(offences)
    )


def test_the_guard_detects_a_reintroduced_fork(tmp_path):
    fork = tmp_path / "fork.py"
    fork.write_text('WEIGHTS = {"contender": 0.5, "rebuild": 0.05, "tank": 0.0}\nPAIRS = {"rebuild": (1.0, 2), "tank": (1, -1.5)}\n')
    labels = tmp_path / "labels.py"
    labels.write_text('LABELS = {"rebuild": "Rebuilding", "tank": "Tanking"}\nGROUP = {"tank": "rebuild", "retool": "retool"}\n')
    assert len(_offences(fork, tmp_path)) == 2
    assert _offences(labels, tmp_path) == []
