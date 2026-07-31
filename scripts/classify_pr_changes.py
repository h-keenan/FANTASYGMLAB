"""Classify whether a change requires deterministic browser validation."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


UI_PATH_RULES = (
    re.compile(r"^app\.py$"),
    re.compile(r"^modules/(?:.*_ui|.*_styles)\.py$"),
    re.compile(r"^modules/(?:application_shell|app_header|app_styles|design_tokens|football_assets|html_rendering|player_cards|player_quick_view|ui_modal|ui_primitives|workspace_ui)\.py$"),
    re.compile(r"^scripts/(?:.*visual_harness|ui_validation_harness|validate_mobile_ui)\.py$"),
    re.compile(r"^tests/test_.*(?:ui|visual|responsive|mobile|modal|shell).*\.py$"),
    re.compile(r"^tests/test_trade_summary_cards\.py$"),
    re.compile(r"^\.github/workflows/(?:ci|auto-merge)\.yml$"),
)


def is_ui_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return any(rule.search(normalized) for rule in UI_PATH_RULES)


def changed_paths(base: str, head: str) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--github-output")
    args = parser.parse_args()
    paths = changed_paths(args.base, args.head)
    ui_paths = tuple(path for path in paths if is_ui_path(path))
    value = "true" if ui_paths else "false"
    print(f"ui_changed={value}")
    print("changed_paths=" + ",".join(paths))
    print("ui_paths=" + ",".join(ui_paths))
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as output:
            output.write(f"ui_changed={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
