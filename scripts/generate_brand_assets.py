#!/usr/bin/env python3
"""Deterministic raster exports for FantasyGM Lab brand assets (Pillow)."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"

BG = (15, 17, 20)
CYAN = (34, 211, 238)
CYAN_DARK = (8, 145, 178)
WHITE = (248, 250, 252)
SLATE1 = (203, 213, 225)
SLATE2 = (148, 163, 184)
INK = (15, 23, 42)
INK2 = (51, 65, 85)
MUTED = (100, 116, 139)


def _font(size: int, *, bold: bool = False):
    names = (
        ("segoeuib.ttf", "arialbd.ttf")
        if bold
        else ("segoeui.ttf", "arial.ttf")
    )
    for name in names:
        for base in (
            Path("C:/Windows/Fonts"),
            Path("/usr/share/fonts/truetype/dejavu"),
            Path("/System/Library/Fonts/Supplemental"),
        ):
            path = base / name
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except OSError:
                    continue
    # DejaVu bold fallback name differs
    for path in (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_command_plate(size: int, *, light: bool = False) -> Image.Image:
    """Canonical Command Plate mark (Candidate A)."""

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bg = WHITE if light else BG
    cyan = CYAN_DARK if light else CYAN
    bar1 = INK if light else WHITE
    bar2 = INK2 if light else SLATE1
    bar3 = MUTED if light else SLATE2
    r = max(2, size // 7)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=bg)
    spine_w = max(2, size // 9)
    draw.rounded_rectangle((0, 0, spine_w, size - 1), radius=max(1, spine_w // 2), fill=cyan)
    pad = size // 4
    h = max(2, size // 16)
    gap = max(3, size // 8)
    y = pad
    widths = (0.72, 0.55, 0.38)
    colors = (bar1, bar2, bar3)
    for width_frac, color in zip(widths, colors):
        w = int((size - pad - spine_w) * width_frac)
        draw.rounded_rectangle((pad, y, pad + w, y + h), radius=1, fill=color)
        y += gap
    cx = int(size * 0.75)
    cy = int(size * 0.66)
    rad = max(3, size // 10)
    draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=cyan, width=max(2, size // 20))
    return img


def draw_signal_grid(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = max(2, size // 7)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=BG)
    grid = (51, 65, 85)
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
    draw.line(pts, fill=CYAN, width=max(2, size // 18), joint="curve")
    cx, cy = pts[-1]
    rad = max(3, size // 14)
    draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=WHITE)
    return img


def draw_ledger_bars(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = max(2, size // 7)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=BG)
    draw.rounded_rectangle(
        (int(size * 0.22), int(size * 0.19), int(size * 0.78), int(size * 0.24)),
        radius=1,
        fill=WHITE,
    )
    bars = (
        (0.22, 0.59, 0.38, 0.81, (100, 116, 139)),
        (0.42, 0.44, 0.58, 0.81, SLATE2),
        (0.62, 0.25, 0.78, 0.81, CYAN),
    )
    for x0, y0, x1, y1, color in bars:
        draw.rounded_rectangle(
            (int(size * x0), int(size * y0), int(size * x1), int(size * y1)),
            radius=max(1, size // 32),
            fill=color,
        )
    return img


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


def write_ico(path: Path, sizes: tuple[int, ...] = (16, 32, 48)) -> None:
    """Minimal multi-size ICO writer (RGBA PNGs embedded)."""

    images = [draw_command_plate(size).convert("RGBA") for size in sizes]
    # Build ICO manually with PNG payloads (Vista+).
    entries = []
    payloads = []
    offset = 6 + 16 * len(images)
    for image in images:
        buf = __import__("io").BytesIO()
        image.save(buf, format="PNG")
        data = buf.getvalue()
        w, h = image.size
        entries.append((w if w < 256 else 0, h if h < 256 else 0, len(data), offset))
        payloads.append(data)
        offset += len(data)
    out = bytearray()
    out += struct.pack("<HHH", 0, 1, len(images))
    for w, h, size, off in entries:
        out += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, size, off)
    for payload in payloads:
        out += payload
    path.write_bytes(bytes(out))


def make_primary(size_h: int = 128, *, light: bool = False) -> Image.Image:
    mark = draw_command_plate(size_h, light=light)
    font = _font(int(size_h * 0.42), bold=True)
    text = "FantasyGM Lab"
    # Estimate text width
    probe = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(probe)
    box = d.textbbox((0, 0), text, font=font)
    tw = box[2] - box[0]
    pad = size_h // 6
    width = size_h + pad + tw + pad
    canvas = Image.new("RGBA", (width, size_h), (0, 0, 0, 0))
    canvas.paste(mark, (0, 0), mark)
    draw = ImageDraw.Draw(canvas)
    color = INK if light else WHITE
    draw.text((size_h + pad, size_h // 2 - (box[3] - box[1]) // 2), text, font=font, fill=color)
    return canvas


def make_founder_lockup(height: int = 96) -> Image.Image:
    mark = draw_command_plate(height)
    title_font = _font(int(height * 0.28), bold=True)
    badge_font = _font(int(height * 0.2), bold=True)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tw = probe.textbbox((0, 0), "FantasyGM Lab", font=title_font)[2]
    pad = height // 5
    width = height + pad + max(tw, 160) + pad
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.paste(mark, (0, 0), mark)
    draw = ImageDraw.Draw(canvas)
    draw.text((height + pad, int(height * 0.18)), "FantasyGM Lab", font=title_font, fill=WHITE)
    draw.text((height + pad, int(height * 0.58)), "FOUNDER BETA", font=badge_font, fill=SLATE2)
    return canvas


def make_og(width: int = 1200, height: int = 630) -> Image.Image:
    canvas = Image.new("RGB", (width, height), (5, 6, 7))
    draw = ImageDraw.Draw(canvas)
    # Atmosphere
    draw.rectangle((0, 0, width, height), fill=(9, 10, 12))
    draw.rectangle((0, 0, 12, height), fill=CYAN)
    mark = draw_command_plate(160)
    canvas.paste(mark, (72, 180), mark)
    title = _font(64, bold=True)
    body = _font(34)
    small = _font(26, bold=True)
    draw.text((270, 200), "FantasyGM Lab", font=title, fill=WHITE)
    draw.text((270, 290), "Your fantasy football front office", font=body, fill=SLATE1)
    draw.text((270, 360), "FOUNDER BETA", font=small, fill=SLATE2)
    draw.text((72, height - 70), "fantasygmlab.com", font=body, fill=CYAN)
    return canvas


def main() -> int:
    BRAND.mkdir(parents=True, exist_ok=True)
    save_png(draw_command_plate(512), BRAND / "fantasygm-lab-mark.png")
    save_png(draw_command_plate(512, light=True), BRAND / "fantasygm-lab-mark-light.png")
    save_png(draw_command_plate(128), BRAND / "share-card-mark.png")
    save_png(draw_command_plate(64), BRAND / "favicon.png")
    save_png(draw_command_plate(32), BRAND / "favicon-32.png")
    save_png(draw_command_plate(16), BRAND / "favicon-16.png")
    write_ico(BRAND / "favicon.ico", (16, 32, 48))
    save_png(make_primary(128), BRAND / "fantasygm-lab-primary.png")
    save_png(make_primary(128, light=True), BRAND / "fantasygm-lab-primary-light.png")
    save_png(make_founder_lockup(96), BRAND / "fantasygm-lab-founder-beta.png")
    save_png(make_og(), BRAND / "og-founder-beta.png")
    # Candidate PNG previews
    cand = BRAND / "candidates"
    save_png(draw_command_plate(256), cand / "a-command-plate.png")
    save_png(draw_signal_grid(256), cand / "b-signal-grid.png")
    save_png(draw_ledger_bars(256), cand / "c-ledger-bars.png")
    # Also publish favicon at repo root for production static probes.
    save_png(draw_command_plate(64), ROOT / "favicon.png")
    write_ico(ROOT / "favicon.ico", (16, 32, 48))
    print("Wrote brand rasters to", BRAND)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
