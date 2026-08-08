#!/usr/bin/env python3
"""Local visual QA board for the FGL Arc Monogram brand system."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_brand_assets import (  # noqa: E402
    BG,
    CYAN,
    WHITE,
    _font,
    draw_brand_mark,
    make_og,
)

OUT = ROOT / "artifacts" / "brand-qa"


def _label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str) -> None:
    draw.text(xy, text, font=_font(14, bold=True), fill=(148, 163, 184))


def size_row() -> Image.Image:
    sizes = (16, 24, 32, 44, 64, 128, 256, 512)
    cell = 140
    canvas = Image.new("RGB", (cell * len(sizes) + 40, 220), (13, 17, 23))
    draw = ImageDraw.Draw(canvas)
    _label(draw, (20, 12), "Mark sizes (compact ≤40, full above)")
    x = 20
    for size in sizes:
        mark = draw_brand_mark(size, compact=size <= 40)
        disp = mark.resize((96, 96), Image.Resampling.NEAREST if size <= 32 else Image.Resampling.LANCZOS)
        canvas.paste(disp, (x, 48), disp)
        _label(draw, (x, 160), f"{size}px")
        x += cell
    return canvas


def mono_row() -> Image.Image:
    canvas = Image.new("RGB", (720, 220), (13, 17, 23))
    draw = ImageDraw.Draw(canvas)
    _label(draw, (20, 12), "Color / light / white-on-dark / dark-on-light")
    variants = (
        draw_brand_mark(128),
        draw_brand_mark(128, light=True),
        draw_brand_mark(128, monochrome=True),
        draw_brand_mark(128, light=True, monochrome=True),
    )
    x = 20
    for mark in variants:
        canvas.paste(mark, (x, 48), mark)
        x += 160
    return canvas


def shell_strip(width: int, height: int = 64) -> Image.Image:
    canvas = Image.new("RGB", (width, height), (9, 10, 12))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 4, height), fill=CYAN)
    mark = draw_brand_mark(28, compact=True)
    canvas.paste(mark, (16, (height - 28) // 2), mark)
    draw.text((52, height // 2 - 10), "FantasyGM Lab", font=_font(18, bold=True), fill=WHITE)
    draw.rounded_rectangle((width - 72, 14, width - 16, height - 14), radius=4, outline=CYAN)
    draw.text((width - 58, height // 2 - 8), "GM", font=_font(14, bold=True), fill=WHITE)
    return canvas


def context_board() -> Image.Image:
    widths = (320, 390, 430, 768, 1024, 1440)
    rows = []
    for w in widths:
        strip = shell_strip(min(w, 900))
        label = Image.new("RGB", (strip.width, 28), BG)
        ImageDraw.Draw(label).text((8, 6), f"Shell {w}px", font=_font(12, bold=True), fill=(148, 163, 184))
        rows.append(label)
        rows.append(strip)
    # Loading / landing / og thumbs
    loading = Image.new("RGB", (390, 160), BG)
    d = ImageDraw.Draw(loading)
    m = draw_brand_mark(40, compact=True)
    loading.paste(m, (24, 40), m)
    d.text((78, 44), "FantasyGM Lab", font=_font(20, bold=True), fill=WHITE)
    d.text((78, 72), "FOUNDER BETA", font=_font(12, bold=True), fill=(148, 163, 184))
    d.rectangle((24, 120, 360, 128), fill=(42, 46, 54))
    d.rectangle((24, 120, 180, 128), fill=CYAN)
    og = make_og().resize((480, 252), Image.Resampling.LANCZOS)
    fav = Image.new("RGB", (280, 120), BG)
    fd = ImageDraw.Draw(fav)
    fd.text((12, 8), "Favicon 16/32/48/64", font=_font(12, bold=True), fill=(148, 163, 184))
    x = 12
    for size in (16, 32, 48, 64):
        mark = draw_brand_mark(size, compact=True).resize((48, 48), Image.Resampling.NEAREST)
        fav.paste(mark, (x, 40), mark)
        x += 64

    max_w = max(r.width for r in rows)
    extras = (loading, og, fav)
    height = sum(r.height for r in rows) + sum(e.height for e in extras) + 40
    canvas = Image.new("RGB", (max(max_w, 900), height), (5, 6, 7))
    y = 0
    for row in rows:
        canvas.paste(row, (0, y))
        y += row.height
    y += 16
    canvas.paste(loading, (20, y))
    y += loading.height + 12
    canvas.paste(og, (20, y))
    y += og.height + 12
    canvas.paste(fav, (20, y))
    return canvas


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    size_row().save(OUT / "qa-sizes.png")
    mono_row().save(OUT / "qa-mono.png")
    context_board().save(OUT / "qa-contexts.png")
    # Combined board
    a = Image.open(OUT / "qa-sizes.png")
    b = Image.open(OUT / "qa-mono.png")
    c = Image.open(OUT / "qa-contexts.png")
    w = max(a.width, b.width, c.width)
    h = a.height + b.height + c.height + 24
    board = Image.new("RGB", (w, h), (5, 6, 7))
    y = 0
    for img in (a, b, c):
        board.paste(img, (0, y))
        y += img.height + 8
    board.save(OUT / "brand-qa-board.png")
    print("Wrote", OUT / "brand-qa-board.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
