"""Guard: no module defines its own float coercer; use ``modules/coerce.py``.

The band-aid audit (docs/audits/2026-11-band-aid-audit.md, item 7) found 32 private ``_num`` / ``_safe_float`` /
``safe_float`` / ``_float`` helpers whose NaN, exception and None semantics all differed. They now live in
``modules/coerce.py`` as named variants. This fails on a new function (or lambda assignment) with one of those
coercer names anywhere under ``modules/`` or ``services/`` except ``modules/coerce.py``.

``modules/sim`` is allowlisted: ``tests/test_sim_isolation.py`` pins each sim file to a per-file import allowlist, and
the engine must stay pure/replay-deterministic, so it keeps its two private ``_num`` copies. Every allowlist entry
must still match a live definition (the guard fails on a stale entry, so the list can only shrink).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COERCE = ROOT / "modules" / "coerce.py"
NAME = re.compile(r"^_?(num|float|safe_float|to_float|as_float|coerce_float|parse_float)$")

ALLOW = {
    "modules/sim/game_setup.py": {"_num"},
    "modules/sim/inputs.py": {"_num"},
}


def _definitions(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and NAME.match(node.name):
            found.add(node.name)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Lambda):
            found.update(t.id for t in node.targets if isinstance(t, ast.Name) and NAME.match(t.id))
    return found


def _all() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for base in ("modules", "services"):
        for path in sorted((ROOT / base).rglob("*.py")):
            if path == COERCE:
                continue
            defs = _definitions(path)
            if defs:
                out[path.relative_to(ROOT).as_posix()] = defs
    return out


def test_no_new_local_float_coercers():
    offenders = {rel: sorted(names - ALLOW.get(rel, set())) for rel, names in _all().items()}
    offenders = {rel: names for rel, names in offenders.items() if names}
    assert not offenders, f"define float coercion in modules/coerce.py, not locally: {offenders}"


def test_allowlist_has_no_stale_entries():
    live = _all()
    stale = {rel: sorted(names - live.get(rel, set())) for rel, names in ALLOW.items()}
    stale = {rel: names for rel, names in stale.items() if names}
    assert not stale, f"remove these entries, the local coercer is gone: {stale}"
