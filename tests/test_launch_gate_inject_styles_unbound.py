"""Regression: nested inject_global_styles import must not shadow main()."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8-sig")


def _direct_body_import_lines(fn: ast.FunctionDef, name: str) -> list[int]:
    """Imports in fn body that bind ``name`` as a local of ``fn`` (not nested defs)."""

    nested_def_nodes = {
        child
        for child in ast.walk(fn)
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and child is not fn
    }

    def _inside_nested(node: ast.AST) -> bool:
        for nested in nested_def_nodes:
            for child in ast.walk(nested):
                if child is node:
                    return True
        return False

    lines: list[int] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.ImportFrom):
            continue
        if _inside_nested(node):
            continue
        if any(alias.name == name for alias in node.names):
            lines.append(node.lineno)
    return lines


def test_main_does_not_locally_import_inject_global_styles():
    tree = ast.parse(APP)
    main_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    local_imports = _direct_body_import_lines(main_fn, "inject_global_styles")
    assert local_imports == [], (
        "Local inject_global_styles import inside main() shadows the module "
        f"binding and crashes cold startup: lines {local_imports}"
    )


def test_module_level_inject_global_styles_import_present():
    assert "from modules.html_rendering import inject_global_styles" in APP.split(
        "def main():", 1
    )[0]


def test_trade_analyzer_still_injects_route_css():
    start = APP.index('if current_page == "trade_analyzer":')
    block = APP[start : APP.index('if current_page == "premium":', start)]
    assert "TRADE_ANALYZER_CSS" in block
    assert "inject_global_styles(TRADE_ANALYZER_CSS)" in block
