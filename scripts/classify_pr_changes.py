"""Classify which CI jobs (mobile app, web-next) a change needs to run."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


MOBILE_APP_PATH_RULES = (re.compile(r"^mobile/"),)
WEB_NEXT_PATH_RULES = (re.compile(r"^web-next/"),)


def is_mobile_app_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return any(rule.search(normalized) for rule in MOBILE_APP_PATH_RULES)


def is_web_next_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return any(rule.search(normalized) for rule in WEB_NEXT_PATH_RULES)


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
    mobile_app_paths = tuple(path for path in paths if is_mobile_app_path(path))
    web_next_paths = tuple(path for path in paths if is_web_next_path(path))
    mobile_app_value = "true" if mobile_app_paths else "false"
    web_next_value = "true" if web_next_paths else "false"
    print(f"mobile_app_changed={mobile_app_value}")
    print(f"web_next_changed={web_next_value}")
    print("changed_paths=" + ",".join(paths))
    print("mobile_app_paths=" + ",".join(mobile_app_paths))
    print("web_next_paths=" + ",".join(web_next_paths))
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as output:
            output.write(f"mobile_app_changed={mobile_app_value}\n")
            output.write(f"web_next_changed={web_next_value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
