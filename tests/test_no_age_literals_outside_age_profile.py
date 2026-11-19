"""Guard: no age-cutoff literal may be compared with an ``age`` value outside ``modules/age_profile.py``.

The audit (docs/audits/2026-11-band-aid-audit.md, item 3) found 22 hardcoded ``age <= 25``-style cutoffs next to the
canonical age vocabulary, so one player could be "young" on one screen and "old" on the next. Every cutoff now lives in
``modules/age_profile.py`` (a position-aware helper, or a named, documented flat cutoff) and call sites read it from
there. This test fails when a numeric literal (other than 0) is compared with a name that is an age (``age``,
``ages``, ``incoming_age``, ``receive_avg_age`` ...). Durations (``age_seconds``, ``age_days`` ...) are not player ages. The simulation package is exempt: it has its own aging model.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGE_PROFILE = ROOT / "modules" / "age_profile.py"
DURATION_TOKENS = {"seconds", "second", "days", "day", "ms", "hours", "minutes", "weeks", "sec", "secs"}


def _is_age_name(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):  # e.g. _asset_age(asset) <= 25
        node = node.func
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Attribute):
        name = node.attr
    else:
        return False
    tokens = name.lower().split("_")
    return bool({"age", "ages"} & set(tokens)) and not (DURATION_TOKENS & set(tokens))


def _numeric_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value != 0
    return False


def _offences(path: Path, root: Path = ROOT) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        if any(_is_age_name(o) for o in operands) and any(_numeric_literal(o) for o in operands):
            found.append(f"{path.relative_to(root)}:{node.lineno}")
    return found


SIM = ROOT / "modules" / "sim"  # the simulation's aging model is pinned by game_rules, not age_profile


def _sources():
    for base in ("modules", "services"):
        for path in sorted((ROOT / base).rglob("*.py")):
            if path != AGE_PROFILE and SIM not in path.parents:
                yield path


def test_no_age_cutoff_literals_outside_age_profile():
    offences = [o for path in _sources() for o in _offences(path)]
    assert not offences, (
        "Age cutoffs belong in modules/age_profile.py (a position-aware helper or a named flat cutoff): "
        + ", ".join(offences)
    )


def test_guard_catches_a_literal(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def f(age, age_days):\n    if 0 < age <= 25:\n        return 1\n    return age_days > 30\n")
    assert _offences(bad, root=tmp_path) == ["bad.py:2"]


def test_guard_allows_named_constants_and_durations(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text(
        "from modules import age_profile\n"
        "def f(age, age_seconds):\n"
        "    return age <= age_profile.CORE_YOUNG_MAX_AGE or age_seconds > 86400 or age <= 0\n"
    )
    assert _offences(ok, root=tmp_path) == []
