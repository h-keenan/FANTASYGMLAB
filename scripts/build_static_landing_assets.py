#!/usr/bin/env python3
"""Copy and optimize brand/marketing assets for static/landing/.

Idempotent: re-running overwrites the same targets with the same sources.

Usage:
  python scripts/build_static_landing_assets.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
MARKETING = ROOT / "assets" / "marketing"
OUT = ROOT / "static" / "landing" / "assets"
WEB = OUT / "web"

MARK_SRC = BRAND / "fantasygm-lab-mark-compact.svg"
FAVICON_SRC = BRAND / "favicon.png"
OG_CANDIDATES = (
    BRAND / "og-founder-beta.png",
    MARKETING / "launch" / "og-founder-beta-launch.png",
)

SHARE_JPGS = (
    "player-share.jpg",
    "trade-share.jpg",
    "waiver-share.jpg",
    "dashboard-desktop.jpg",
)

MAX_WIDTH = 960
JPEG_QUALITY = 72


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"  copied {src.relative_to(ROOT)} -> {dest.relative_to(ROOT)} ({dest.stat().st_size} bytes)")


def _resolve_og() -> Path:
    for candidate in OG_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "No OG image found. Expected one of:\n  "
        + "\n  ".join(str(p.relative_to(ROOT)) for p in OG_CANDIDATES)
    )


def _write_web_jpg(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        shutil.copy2(src, dest)
        print(f"  (no Pillow) copied {src.name} -> {dest.relative_to(ROOT)}")
        return

    with Image.open(src) as img:
        img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
        if img.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(img.width)
            img = img.resize((MAX_WIDTH, max(1, int(img.height * ratio))), Image.Resampling.LANCZOS)
        img.save(dest, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    print(f"  optimized {src.name} -> {dest.relative_to(ROOT)} ({dest.stat().st_size} bytes)")


def main() -> int:
    print("Building static landing assets…")
    OUT.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)

    if not MARK_SRC.is_file():
        raise FileNotFoundError(MARK_SRC)
    if not FAVICON_SRC.is_file():
        raise FileNotFoundError(FAVICON_SRC)

    _copy_file(MARK_SRC, OUT / "fantasygm-lab-mark-compact.svg")
    _copy_file(FAVICON_SRC, OUT / "favicon.png")
    og = _resolve_og()
    _copy_file(og, OUT / "og-founder-beta.png")

    for name in SHARE_JPGS:
        src = MARKETING / name
        if not src.is_file():
            print(f"  skip missing {src.relative_to(ROOT)}")
            continue
        _copy_file(src, OUT / name)
        _write_web_jpg(src, WEB / name)

    print("Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI exit path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
