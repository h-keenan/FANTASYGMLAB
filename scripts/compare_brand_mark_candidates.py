#!/usr/bin/env python3
"""Render A/B/C brand marks in product contexts for founder selection."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_brand_assets import (  # noqa: E402
    CYAN,
    CYAN_DARK,
    INK,
    SLATE1,
    SLATE2,
    WHITE,
    _font,
    draw_command_plate,
    draw_ledger_bars,
    draw_signal_grid,
)


OUT = ROOT / "artifacts" / "brand-mark-comparison"
DRAWERS = {
    "Command Plate (selected)": draw_command_plate,
    "Signal Grid (rejected)": draw_signal_grid,
    "Ledger Bars (rejected)": draw_ledger_bars,
}


def _mark(name: str, size: int, *, light: bool = False) -> Image.Image:
    drawer = DRAWERS[name]
    if name.startswith("Command Plate"):
        return drawer(size, light=light)
    if not light:
        return drawer(size)
    if name.startswith("Signal Grid"):
        return _signal_light(size)
    return _ledger_light(size)


def _signal_light(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = max(2, size // 7)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=WHITE)
    grid = (203, 213, 225)
    for frac in (0.28, 0.5, 0.72):
        y = int(size * frac)
        x = int(size * frac)
        draw.line((int(size * 0.22), y, int(size * 0.78), y), fill=grid, width=max(1, size // 40))
        draw.line((x, int(size * 0.18), x, int(size * 0.82)), fill=grid, width=max(1, size // 40))
    pts = [
        (int(size * 0.28), int(size * 0.69)),
        (int(size * 0.44), int(size * 0.53)),
        (int(size * 0.59), int(size * 0.59)),
        (int(size * 0.75), int(size * 0.31)),
    ]
    draw.line(pts, fill=CYAN_DARK, width=max(2, size // 18), joint="curve")
    cx, cy = pts[-1]
    rad = max(3, size // 14)
    draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=INK)
    return img


def _ledger_light(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = max(2, size // 7)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=WHITE)
    draw.rounded_rectangle(
        (int(size * 0.22), int(size * 0.19), int(size * 0.78), int(size * 0.24)),
        radius=1,
        fill=INK,
    )
    bars = (
        (0.22, 0.59, 0.38, 0.81, (148, 163, 184)),
        (0.42, 0.44, 0.58, 0.81, (100, 116, 139)),
        (0.62, 0.25, 0.78, 0.81, CYAN_DARK),
    )
    for x0, y0, x1, y1, color in bars:
        draw.rounded_rectangle(
            (int(size * x0), int(size * y0), int(size * x1), int(size * y1)),
            radius=max(1, size // 32),
            fill=color,
        )
    return img


def _paste(canvas: Image.Image, mark: Image.Image, xy: tuple[int, int]) -> None:
    canvas.paste(mark, xy, mark)


def shell_strip(name: str, width: int, height: int = 72) -> Image.Image:
    canvas = Image.new("RGB", (width, height), (5, 6, 7))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, height), fill=(9, 10, 12))
    draw.rectangle((0, 0, 4, height), fill=CYAN)
    mark = _mark(name, 28)
    _paste(canvas, mark, (16, (height - 28) // 2))
    font = _font(22, bold=True)
    small = _font(14, bold=True)
    draw.text((56, 14), "Trade Hub", font=font, fill=WHITE)
    draw.text((56, 42), "War Room  ·  Fixture League", font=small, fill=SLATE2)
    draw.rounded_rectangle((width - 118, 22, width - 16, 50), radius=2, fill=(15, 17, 20), outline=(42, 46, 53))
    draw.text((width - 108, 28), "FOUNDER BETA", font=_font(12, bold=True), fill=SLATE2)
    return canvas


def gm_control(name: str) -> Image.Image:
    canvas = Image.new("RGB", (120, 80), (5, 6, 7))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((38, 18, 82, 62), radius=4, fill=(15, 17, 20), outline=(226, 232, 240))
    draw.rectangle((38, 18, 41, 62), fill=CYAN)
    mark = _mark(name, 18)
    _paste(canvas, mark, (44, 24))
    draw.text((48, 46), "GM", font=_font(12, bold=True), fill=WHITE)
    return canvas


def loading(name: str) -> Image.Image:
    canvas = Image.new("RGB", (420, 240), (5, 6, 7))
    draw = ImageDraw.Draw(canvas)
    mark = _mark(name, 40)
    _paste(canvas, mark, (190, 48))
    draw.text((120, 104), "FantasyGM Lab", font=_font(28, bold=True), fill=WHITE)
    draw.text((155, 142), "FOUNDER BETA", font=_font(14, bold=True), fill=SLATE2)
    draw.text((145, 178), "Loading league...", font=_font(16), fill=SLATE1)
    return canvas


def favicon_row(name: str) -> Image.Image:
    canvas = Image.new("RGB", (260, 90), (5, 6, 7))
    draw = ImageDraw.Draw(canvas)
    x = 20
    for size in (16, 32, 64):
        mark = _mark(name, size)
        _paste(canvas, mark, (x, (90 - size) // 2))
        draw.text((x, 72), f"{size}", font=_font(11), fill=SLATE2)
        x += size + 28
    return canvas


def share_card(name: str, kind: str) -> Image.Image:
    canvas = Image.new("RGB", (640, 360), (5, 6, 7))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((16, 16, 624, 344), radius=16, fill=(15, 17, 20))
    mark = _mark(name, 36)
    _paste(canvas, mark, (40, 36))
    draw.text((90, 44), "FantasyGM Lab", font=_font(20, bold=True), fill=WHITE)
    title = "TRADE PATH" if kind == "trade" else "WAIVER ADD"
    draw.text((40, 90), title, font=_font(16, bold=True), fill=SLATE2)
    hero = "Player A  →  Player B" if kind == "trade" else "Add  ·  Player X"
    draw.text((40, 130), hero, font=_font(32, bold=True), fill=WHITE)
    draw.rounded_rectangle((40, 200, 600, 270), radius=10, fill=(27, 30, 35))
    reason = "Canonical reason only." if kind == "trade" else "Upside stash before the window closes."
    draw.text((56, 224), reason, font=_font(18), fill=SLATE1)
    draw.text((40, 300), "fantasygmlab.com  ·  Founder Beta", font=_font(14), fill=CYAN)
    return canvas


def og(name: str) -> Image.Image:
    canvas = Image.new("RGB", (1200, 630), (5, 6, 7))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 12, 630), fill=CYAN)
    mark = _mark(name, 160)
    _paste(canvas, mark, (72, 180))
    draw.text((270, 200), "FantasyGM Lab", font=_font(64, bold=True), fill=WHITE)
    draw.text((270, 290), "Your fantasy football front office", font=_font(34), fill=SLATE1)
    draw.text((270, 360), "FOUNDER BETA", font=_font(26, bold=True), fill=SLATE2)
    draw.text((72, 560), "fantasygmlab.com", font=_font(34), fill=CYAN)
    return canvas


def founder_lockup(name: str) -> Image.Image:
    canvas = Image.new("RGB", (420, 120), (5, 6, 7))
    mark = _mark(name, 72)
    _paste(canvas, mark, (24, 24))
    draw = ImageDraw.Draw(canvas)
    draw.text((112, 30), "FantasyGM Lab", font=_font(28, bold=True), fill=WHITE)
    draw.text((112, 70), "FOUNDER BETA", font=_font(18, bold=True), fill=SLATE2)
    return canvas


def premium(name: str) -> Image.Image:
    canvas = Image.new("RGB", (480, 160), (5, 6, 7))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((16, 16, 464, 144), radius=8, fill=(15, 17, 20), outline=(250, 204, 21))
    mark = _mark(name, 40)
    _paste(canvas, mark, (36, 40))
    draw.text((92, 40), "FantasyGM Lab Premium", font=_font(24, bold=True), fill=WHITE)
    draw.text((92, 78), "Tier of the same brand — not a separate logo.", font=_font(16), fill=SLATE1)
    draw.rounded_rectangle((92, 108, 168, 132), radius=2, fill=(42, 32, 8), outline=(250, 204, 21))
    draw.text((104, 112), "PREMIUM", font=_font(12, bold=True), fill=(250, 204, 21))
    return canvas


def dark_light(name: str) -> Image.Image:
    canvas = Image.new("RGB", (280, 140), (5, 6, 7))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 140, 140), fill=(5, 6, 7))
    draw.rectangle((140, 0, 280, 140), fill=(248, 250, 252))
    _paste(canvas, _mark(name, 64), (38, 38))
    _paste(canvas, _mark(name, 64, light=True), (178, 38))
    return canvas


def label_banner(text: str, width: int) -> Image.Image:
    canvas = Image.new("RGB", (width, 36), (15, 17, 20))
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 8), text, font=_font(18, bold=True), fill=WHITE)
    return canvas


def stack_labeled(parts: list[tuple[str, Image.Image]], gap: int = 12) -> Image.Image:
    width = max(img.width for _, img in parts)
    height = sum(36 + img.height + gap for _, img in parts) + gap
    canvas = Image.new("RGB", (width + 24, height), (27, 30, 35))
    y = gap
    for title, img in parts:
        banner = label_banner(title, width)
        canvas.paste(banner, (12, y))
        y += 36
        canvas.paste(img, (12, y))
        y += img.height + gap
    return canvas


def candidate_board(name: str) -> Image.Image:
    parts = [
        ("Executive shell 390", shell_strip(name, 390)),
        ("Executive shell 1440", shell_strip(name, 1440).resize((720, 36), Image.Resampling.LANCZOS)),
        ("GM control 44px target", gm_control(name)),
        ("Favicon 16 / 32 / 64", favicon_row(name)),
        ("Loading screen", loading(name)),
        ("Share Trade card", share_card(name, "trade")),
        ("Share Waiver card", share_card(name, "waiver")),
        ("OG 1200×630 (half)", og(name).resize((600, 315), Image.Resampling.LANCZOS)),
        ("Founder Beta lockup", founder_lockup(name)),
        ("Premium surface", premium(name)),
        ("Dark / light", dark_light(name)),
    ]
    return stack_labeled(parts)


def contact_sheet() -> Image.Image:
    """Side-by-side favicon + shell contact for scoring."""

    names = list(DRAWERS)
    cell_w, cell_h = 320, 420
    canvas = Image.new("RGB", (cell_w * 3 + 40, cell_h + 40), (27, 30, 35))
    draw = ImageDraw.Draw(canvas)
    for i, name in enumerate(names):
        x = 20 + i * cell_w
        draw.text((x, 12), name, font=_font(16, bold=True), fill=WHITE)
        y = 40
        for size in (64, 32, 16):
            _paste(canvas, _mark(name, size), (x + 20, y))
            draw.text((x + 100, y + size // 2 - 8), f"{size}px dark", font=_font(14), fill=SLATE1)
            _paste(canvas, _mark(name, size, light=True), (x + 200, y))
            y += size + 18
        shell = shell_strip(name, 300)
        canvas.paste(shell, (x + 10, y + 8))
    return canvas


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    save = lambda img, name: img.save(OUT / name, format="PNG", optimize=True)
    save(contact_sheet(), "contact-sheet.png")
    for name, slug in (
        ("Command Plate (selected)", "command-plate"),
        ("Signal Grid (rejected)", "signal-grid"),
        ("Ledger Bars (rejected)", "ledger-bars"),
    ):
        board = candidate_board(name)
        save(board, f"board-{slug}.png")
        save(favicon_row(name), f"favicon-{slug}.png")
        save(shell_strip(name, 390), f"shell-390-{slug}.png")
        save(shell_strip(name, 1440), f"shell-1440-{slug}.png")
        save(share_card(name, "trade"), f"share-trade-{slug}.png")
        save(share_card(name, "waiver"), f"share-waiver-{slug}.png")
        save(og(name), f"og-{slug}.png")
        save(dark_light(name), f"dark-light-{slug}.png")
    print("Wrote comparison boards to", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
