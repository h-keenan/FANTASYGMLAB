"""Scan for top-level modules with no external importers.

Used by repository hygiene validation. Not a CI gate by itself — tests assert
the scan reports zero unused candidates after Class A deletions.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"__init__"}


def main() -> None:
    modules = sorted(
        p.stem
        for p in (ROOT / "modules").glob("*.py")
        if p.stem not in SKIP
    )
    files = (
        [ROOT / "app.py"]
        + list((ROOT / "modules").rglob("*.py"))
        + list((ROOT / "scripts").rglob("*.py"))
        + list((ROOT / "tests").rglob("*.py"))
    )
    unused: list[str] = []
    for name in modules:
        needles = (
            f"import {name}",
            f"from modules import {name}",
            f"from modules.{name}",
            f"modules.{name}",
            f"modules/{name}.py",
            f"modules\\\\{name}.py",
        )
        hit = False
        for path in files:
            if path.name == f"{name}.py" and path.parent.name == "modules":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(needle in text for needle in needles):
                hit = True
                break
        if not hit:
            unused.append(name)
    print("UNUSED_MODULE_CANDIDATES", len(unused))
    for name in unused:
        print(name)


if __name__ == "__main__":
    main()
