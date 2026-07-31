"""Generate a deterministic, sanitized performance-boundary inventory."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_PATHS = (ROOT / "app.py", *sorted((ROOT / "modules").rglob("*.py")))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def inventory() -> dict:
    caches: list[dict] = []
    reruns: list[dict] = []
    timing_labels: set[str] = set()
    for path in PYTHON_PATHS:
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    name = _call_name(decorator)
                    if name in {"st.cache_data", "st.cache_resource", "functools.lru_cache", "lru_cache"}:
                        caches.append({"file": relative, "line": node.lineno, "function": node.name, "kind": name})
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name == "st.rerun":
                reruns.append({"file": relative, "line": node.lineno})
            if name in {"performance.time_block", "performance.record_timing", "performance.timed_call"} and node.args:
                label = node.args[0]
                if isinstance(label, ast.Constant) and isinstance(label.value, str):
                    timing_labels.add(label.value)
    return {
        "schema": "dynastygm-performance-boundary-audit-v1",
        "cache_count": len(caches),
        "caches": sorted(caches, key=lambda item: (item["file"], item["line"])),
        "explicit_rerun_count": len(reruns),
        "explicit_reruns": sorted(reruns, key=lambda item: (item["file"], item["line"])),
        "timing_labels": sorted(timing_labels),
        "privacy": "Static file paths, function names, and line numbers only.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    serialized = json.dumps(inventory(), indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
