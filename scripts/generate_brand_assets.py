#!/usr/bin/env python3
"""Deterministic FantasyGM Lab brand assets — FGL Arc Monogram (Pillow + SVG).

Regenerate production rasters/vectors:
    python scripts/generate_brand_assets.py

Requires only Pillow (and stdlib). No proprietary desktop software.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
ICONS = BRAND / "icons"
ARCHIVE_CP = BRAND / "archive" / "command-plate"

# Canonical palette (consolidated with design_tokens / brand_identity)
BG = (15, 17, 20)  # #0F1114 surface plate
BG_DEEP = (5, 6, 7)  # #050607
CYAN = (34, 211, 238)  # #22D3EE Analyze — existing brand cyan
YELLOW = (250, 204, 21)  # #FACC15 Project — existing action/premium gold
RED = (239, 68, 68)  # #EF4444 Execute — existing danger (brand language only)
WHITE = (242, 244, 247)  # #F2F4F7
SLATE1 = (203, 213, 225)
SLATE2 = (148, 163, 184)
INK = (15, 23, 42)
MUTED = (100, 116, 139)


def _font(size: int, *, bold: bool = False):
    names = (
        ("DejaVuSans-Bold.ttf", "segoeuib.ttf", "arialbd.ttf", "Inter-Bold.ttf")
        if bold
        else ("DejaVuSans.ttf", "segoeui.ttf", "arial.ttf", "Inter-Regular.ttf")
    )
    bases = (
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/inter"),
        Path("C:/Windows/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
        Path("/usr/share/fonts/truetype/liberation"),
    )
    for name in names:
        for base in bases:
            path = base / name
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except OSError:
                    continue
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


def _hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _arc_points(
    size: int,
    *,
    lift: float,
    reach: float,
    samples: int = 28,
) -> list[tuple[float, float]]:
    """Quadratic-ish arc from shared origin toward upper-right."""

    # Shared origin just left of the F stem / baseline cluster
    ox = size * 0.10
    oy = size * 0.70
    ex = size * reach
    ey = size * (0.18 + lift)
    cx = size * (0.38 + lift * 0.25)
    cy = size * (0.30 + lift * 0.45)
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):
        t = i / samples
        x = (1 - t) * (1 - t) * ox + 2 * (1 - t) * t * cx + t * t * ex
        y = (1 - t) * (1 - t) * oy + 2 * (1 - t) * t * cy + t * t * ey
        pts.append((x, y))
    return pts


def _draw_arrowhead(
    draw: ImageDraw.ImageDraw,
    tip: tuple[float, float],
    prev: tuple[float, float],
    *,
    color: tuple[int, int, int],
    length: float,
) -> None:
    dx = tip[0] - prev[0]
    dy = tip[1] - prev[1]
    mag = math.hypot(dx, dy) or 1.0
    ux, uy = dx / mag, dy / mag
    px, py = -uy, ux
    base_x = tip[0] - ux * length
    base_y = tip[1] - uy * length
    half = length * 0.55
    pts = [
        (tip[0], tip[1]),
        (base_x + px * half, base_y + py * half),
        (base_x - px * half, base_y - py * half),
    ]
    draw.polygon(pts, fill=color)


def draw_brand_mark(
    size: int,
    *,
    light: bool = False,
    monochrome: bool = False,
    compact: bool | None = None,
) -> Image.Image:
    """Canonical FGL Arc Monogram.

    compact=True forces small-size optical adjustments (thicker strokes, no
    arrowheads, larger FGL). When compact is None, auto-enable below 48px.
    """

    if compact is None:
        compact = size <= 40

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    plate = WHITE if light else BG
    ink = INK if light else WHITE
    r = max(2, size // 7)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=plate)

    if monochrome:
        colors = (ink, ink, ink)
    else:
        # Analyze → Project → Execute (cyan / yellow / red)
        # Light surfaces use slightly deeper cyan for contrast; yellow/red stay
        # readable on white plate.
        cyan = (8, 145, 178) if light else CYAN
        colors = (cyan, YELLOW if not light else (202, 138, 4), RED if not light else (185, 28, 28))

    # Arc geometry: longest/lowest cyan, mid yellow, shortest/highest red
    # lift raises the end Y (screen-down), so smaller lift = higher arc.
    specs = (
        (0.20, 0.92, colors[0]),  # analyze (cyan) — lowest, longest
        (0.10, 0.80, colors[1]),  # project (yellow)
        (0.00, 0.68, colors[2]),  # execute (red) — highest, shortest
    )
    stroke = max(2, int(round(size * (0.08 if compact else 0.052))))
    if compact and size <= 20:
        stroke = max(2, size // 8)

    for lift, reach, color in specs:
        pts = _arc_points(size, lift=lift, reach=reach, samples=20 if compact else 32)
        if compact:
            pts = [(x, y - size * 0.03) for x, y in pts]
        draw.line(pts, fill=color, width=stroke, joint="curve")
        if not compact and size >= 48:
            _draw_arrowhead(draw, pts[-1], pts[-2], color=color, length=max(3.0, size * 0.065))

    # FGL monogram — optically enlarged at tiny sizes; remains readable alone
    font_size = int(size * (0.40 if compact else 0.33))
    if size <= 16:
        font_size = max(7, int(size * 0.46))
    font = _font(font_size, bold=True)
    label = "FGL"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = int(size * (0.12 if compact else 0.13))
    ty = int(size * (0.60 if compact else 0.62)) - (th // 8)
    # Keep within plate
    tx = max(2, min(tx, size - tw - 2))
    ty = max(2, min(ty, size - th - max(1, size // 16)))
    draw.text((tx, ty), label, font=font, fill=ink)
    return img


def draw_command_plate_archived(size: int, *, light: bool = False) -> Image.Image:
    """Archived Command Plate geometry (historical QA only — not production)."""

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bg = WHITE if light else BG
    cyan = (8, 145, 178) if light else CYAN
    bar1 = INK if light else WHITE
    bar2 = (51, 65, 85) if light else SLATE1
    bar3 = MUTED if light else SLATE2
    r = max(2, size // 7)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=bg)
    spine_w = max(2, size // (8 if size <= 24 else 9))
    draw.rounded_rectangle((0, 0, spine_w, size - 1), radius=max(1, spine_w // 2), fill=cyan)
    pad = max(size // 5, spine_w + 2) if size <= 24 else size // 4
    h = max(2, size // (12 if size <= 24 else 16))
    gap = max(2, size // (7 if size <= 24 else 8))
    y = pad
    widths = (0.72, 0.55, 0.38)
    colors = (bar1, bar2, bar3)
    for width_frac, color in zip(widths, colors):
        w = int((size - pad - 1) * width_frac)
        draw.rounded_rectangle((pad, y, pad + w, y + h), radius=1, fill=color)
        y += gap
    cx = int(size * 0.75)
    cy = int(size * 0.66)
    rad = max(2, size // (9 if size <= 24 else 10))
    draw.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=cyan, width=max(2, size // 18))
    return img


# Temporary alias: production callers must use draw_brand_mark (FGL Arc Monogram).
draw_command_plate = draw_brand_mark


def draw_signal_grid(size: int) -> Image.Image:
    """Archived exploration helper (not production)."""

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
    """Archived exploration helper (not production)."""

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

    images = [draw_brand_mark(size, compact=True).convert("RGBA") for size in sizes]
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


def svg_mark(
    *,
    light: bool = False,
    monochrome: bool = False,
    compact: bool = False,
) -> str:
    """Canonical SVG for the FGL Arc Monogram."""

    plate = _hex(WHITE) if light else _hex(BG)
    ink = _hex(INK) if light else _hex(WHITE)
    if monochrome:
        c1 = c2 = c3 = ink
    else:
        c1 = "#0891B2" if light else _hex(CYAN)
        c2 = "#CA8A04" if light else _hex(YELLOW)
        c3 = "#B91C1C" if light else _hex(RED)

    if compact:
        # Optical small-size: thicker arcs, no arrowheads, larger FGL
        paths = (
            (c1, "M7 45 C 26 44, 42 28, 56 18", 4.0),  # cyan lowest/longest
            (c2, "M7 45 C 24 38, 38 24, 50 16", 4.0),
            (c3, "M7 45 C 20 34, 32 22, 44 15", 4.0),  # red highest/shortest
        )
        text = (
            f'<text x="8" y="57" fill="{ink}" font-family="Inter,Segoe UI,system-ui,sans-serif" '
            f'font-size="21" font-weight="800" letter-spacing="-1.4">FGL</text>'
        )
        arrows = ""
    else:
        paths = (
            (c1, "M6 46 C 28 46, 44 28, 58 14", 2.7),
            (c2, "M6 46 C 24 40, 40 24, 52 13", 2.7),
            (c3, "M6 46 C 20 34, 34 22, 46 14", 2.7),
        )
        text = (
            f'<text x="9" y="58" fill="{ink}" font-family="Inter,Segoe UI,system-ui,sans-serif" '
            f'font-size="17" font-weight="800" letter-spacing="-1.1">FGL</text>'
        )
        arrows = (
            f'<path d="M58 14 L54.2 11.8 L55.6 16 Z" fill="{c1}"/>'
            f'<path d="M52 13 L48.5 11.2 L50 15.2 Z" fill="{c2}"/>'
            f'<path d="M46 14 L43 12.4 L44.2 16 Z" fill="{c3}"/>'
        )

    path_svg = "".join(
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        for color, d, sw in paths
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" '
        'aria-label="FantasyGM Lab">'
        f'<rect width="64" height="64" rx="10" fill="{plate}"/>'
        f"{path_svg}{arrows}{text}</svg>"
    )


def svg_primary_horizontal(*, light: bool = False, monochrome: bool = False) -> str:
    """Primary horizontal lockup: [MARK] FANTASY GM LAB with GM in cyan."""

    ink = _hex(INK) if light else _hex(WHITE)
    gm = ink if monochrome else ("#0891B2" if light else _hex(CYAN))
    inner = svg_mark(light=light, monochrome=monochrome, compact=False)
    mark_body = inner[inner.find("<rect") : inner.rfind("</svg>")]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 64" role="img" '
        'aria-label="FantasyGM Lab">'
        f"<g>{mark_body}</g>"
        f'<text x="80" y="40" fill="{ink}" font-family="Inter,Segoe UI,system-ui,sans-serif" '
        f'font-size="26" font-weight="800" letter-spacing="0.04em">FANTASY</text>'
        f'<text x="210" y="40" fill="{gm}" font-family="Inter,Segoe UI,system-ui,sans-serif" '
        f'font-size="26" font-weight="800" letter-spacing="0.04em">GM</text>'
        f'<text x="262" y="40" fill="{ink}" font-family="Inter,Segoe UI,system-ui,sans-serif" '
        f'font-size="26" font-weight="800" letter-spacing="0.04em">LAB</text>'
        "</svg>"
    )


def svg_founder_beta() -> str:
    ink = _hex(WHITE)
    gm = _hex(CYAN)
    mute = _hex(SLATE2)
    inner = svg_mark(compact=False)
    mark_body = inner[inner.find("<rect") : inner.rfind("</svg>")]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 80" role="img" '
        'aria-label="FantasyGM Lab Founder Beta">'
        f"<g>{mark_body}</g>"
        f'<text x="80" y="34" fill="{ink}" font-family="Inter,Segoe UI,system-ui,sans-serif" '
        f'font-size="22" font-weight="800" letter-spacing="0.04em">FANTASY</text>'
        f'<text x="190" y="34" fill="{gm}" font-family="Inter,Segoe UI,system-ui,sans-serif" '
        f'font-size="22" font-weight="800" letter-spacing="0.04em">GM</text>'
        f'<text x="234" y="34" fill="{ink}" font-family="Inter,Segoe UI,system-ui,sans-serif" '
        f'font-size="22" font-weight="800" letter-spacing="0.04em">LAB</text>'
        f'<text x="80" y="58" fill="{mute}" font-family="Inter,Segoe UI,system-ui,sans-serif" '
        f'font-size="12" font-weight="700" letter-spacing="0.14em">FOUNDER BETA</text>'
        "</svg>"
    )


def make_primary(size_h: int = 128, *, light: bool = False, monochrome: bool = False) -> Image.Image:
    mark = draw_brand_mark(size_h, light=light, monochrome=monochrome)
    font = _font(int(size_h * 0.34), bold=True)
    fantasy = "FANTASY"
    gm = "GM"
    lab = "LAB"
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    gap = max(6, size_h // 10)
    tw = (
        probe.textbbox((0, 0), fantasy, font=font)[2]
        + probe.textbbox((0, 0), gm, font=font)[2]
        + probe.textbbox((0, 0), lab, font=font)[2]
        + gap * 2
    )
    pad = size_h // 6
    width = size_h + pad + tw + pad
    canvas = Image.new("RGBA", (width, size_h), (0, 0, 0, 0))
    canvas.paste(mark, (0, 0), mark)
    draw = ImageDraw.Draw(canvas)
    ink = INK if light else WHITE
    accent = ink if monochrome else ((8, 145, 178) if light else CYAN)
    x = size_h + pad
    y = size_h // 2 - int(size_h * 0.18)
    draw.text((x, y), fantasy, font=font, fill=ink)
    x += probe.textbbox((0, 0), fantasy, font=font)[2] + gap
    draw.text((x, y), gm, font=font, fill=accent)
    x += probe.textbbox((0, 0), gm, font=font)[2] + gap
    draw.text((x, y), lab, font=font, fill=ink)
    return canvas


def make_founder_lockup(height: int = 96) -> Image.Image:
    mark = draw_brand_mark(height)
    title_font = _font(int(height * 0.24), bold=True)
    badge_font = _font(int(height * 0.16), bold=True)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tw = probe.textbbox((0, 0), "FANTASY GM LAB", font=title_font)[2]
    pad = height // 5
    width = height + pad + max(tw, 200) + pad
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.paste(mark, (0, 0), mark)
    draw = ImageDraw.Draw(canvas)
    x = height + pad
    draw.text((x, int(height * 0.14)), "FANTASY", font=title_font, fill=WHITE)
    fx = x + probe.textbbox((0, 0), "FANTASY ", font=title_font)[2]
    draw.text((fx, int(height * 0.14)), "GM", font=title_font, fill=CYAN)
    gx = fx + probe.textbbox((0, 0), "GM ", font=title_font)[2]
    draw.text((gx, int(height * 0.14)), "LAB", font=title_font, fill=WHITE)
    draw.text((x, int(height * 0.58)), "FOUNDER BETA", font=badge_font, fill=SLATE2)
    return canvas


def make_og(width: int = 1200, height: int = 630) -> Image.Image:
    """Link-preview OG: FGL Arc Monogram + name + value + Founder Beta."""

    canvas = Image.new("RGB", (width, height), BG_DEEP)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, height), fill=(9, 10, 12))
    draw.rectangle((0, 0, 12, height), fill=CYAN)
    # Restrained trajectory motif (brand language, not product UI)
    for lift, reach, color, width_px in (
        (0.0, 0.55, (*CYAN, 40), 3),
        (0.08, 0.48, (*YELLOW, 36), 3),
        (0.16, 0.40, (*RED, 32), 3),
    ):
        # Soft decorative arcs in the right half — low opacity via thin strokes
        pts = [(width * 0.55 + x * 0.9, height * 0.55 + (y - 200) * 0.85) for x, y in _arc_points(420, lift=lift, reach=reach)]
        draw.line(pts, fill=color[:3], width=width_px, joint="curve")

    mark = draw_brand_mark(160)
    canvas.paste(mark, (72, 150), mark)
    title = _font(56, bold=True)
    body = _font(28)
    small = _font(24, bold=True)
    draw.text((270, 155), "FANTASY", font=title, fill=WHITE)
    tw = draw.textbbox((0, 0), "FANTASY ", font=title)[2]
    draw.text((270 + tw, 155), "GM", font=title, fill=CYAN)
    tw2 = draw.textbbox((0, 0), "GM ", font=title)[2]
    draw.text((270 + tw + tw2, 155), "LAB", font=title, fill=WHITE)
    value = "League-aware recommendations for dynasty managers who want a clear next move."
    words = value.split()
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=body)[2] <= 860:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    y = 250
    for line in lines:
        draw.text((270, y), line, font=body, fill=SLATE1)
        y += 38
    draw.text((270, y + 16), "FOUNDER BETA", font=small, fill=SLATE2)
    draw.text((72, height - 70), "fantasygmlab.com", font=body, fill=CYAN)
    return canvas


def write_svgs() -> None:
    BRAND.mkdir(parents=True, exist_ok=True)
    (BRAND / "fantasygm-lab-mark.svg").write_text(svg_mark(), encoding="utf-8")
    (BRAND / "fantasygm-lab-mark-light.svg").write_text(svg_mark(light=True), encoding="utf-8")
    (BRAND / "fantasygm-lab-mark-dark.svg").write_text(
        svg_mark(monochrome=True), encoding="utf-8"
    )
    # Dark-on-light true one-color (quality gate)
    (BRAND / "fantasygm-lab-mark-mono-light.svg").write_text(
        svg_mark(light=True, monochrome=True), encoding="utf-8"
    )
    (BRAND / "fantasygm-lab-mark-compact.svg").write_text(
        svg_mark(compact=True), encoding="utf-8"
    )
    (BRAND / "fantasygm-lab-primary.svg").write_text(svg_primary_horizontal(), encoding="utf-8")
    (BRAND / "fantasygm-lab-primary-light.svg").write_text(
        svg_primary_horizontal(light=True), encoding="utf-8"
    )
    (BRAND / "fantasygm-lab-primary-dark.svg").write_text(
        svg_primary_horizontal(monochrome=True), encoding="utf-8"
    )
    (BRAND / "fantasygm-lab-founder-beta.svg").write_text(svg_founder_beta(), encoding="utf-8")


def main() -> int:
    BRAND.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)
    ARCHIVE_CP.mkdir(parents=True, exist_ok=True)
    write_svgs()

    save_png(draw_brand_mark(512), BRAND / "fantasygm-lab-mark.png")
    save_png(draw_brand_mark(512, light=True), BRAND / "fantasygm-lab-mark-light.png")
    save_png(draw_brand_mark(512, monochrome=True), BRAND / "fantasygm-lab-mark-dark.png")
    save_png(
        draw_brand_mark(512, light=True, monochrome=True),
        BRAND / "fantasygm-lab-mark-mono-light.png",
    )
    save_png(draw_brand_mark(512, compact=True), BRAND / "fantasygm-lab-mark-compact.png")
    save_png(draw_brand_mark(128, compact=True), BRAND / "share-card-mark.png")
    save_png(draw_brand_mark(64, compact=True), BRAND / "favicon.png")
    save_png(draw_brand_mark(32, compact=True), BRAND / "favicon-32.png")
    save_png(draw_brand_mark(16, compact=True), BRAND / "favicon-16.png")
    write_ico(BRAND / "favicon.ico", (16, 32, 48))

    for px in (512, 256, 192, 180, 128):
        save_png(draw_brand_mark(px, compact=px <= 192), ICONS / f"icon-{px}.png")
    save_png(draw_brand_mark(64, compact=True), ICONS / "favicon-64.png")
    save_png(draw_brand_mark(32, compact=True), ICONS / "favicon-32.png")
    save_png(draw_brand_mark(16, compact=True), ICONS / "favicon-16.png")

    save_png(make_primary(128), BRAND / "fantasygm-lab-primary.png")
    save_png(make_primary(128, light=True), BRAND / "fantasygm-lab-primary-light.png")
    save_png(make_primary(128, monochrome=True), BRAND / "fantasygm-lab-primary-dark.png")
    save_png(make_founder_lockup(96), BRAND / "fantasygm-lab-founder-beta.png")
    save_png(make_og(), BRAND / "og-founder-beta.png")

    # Repo-root favicon copies for static probes
    save_png(draw_brand_mark(64, compact=True), ROOT / "favicon.png")
    write_ico(ROOT / "favicon.ico", (16, 32, 48))

    readme = ARCHIVE_CP / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Archived Command Plate mark\n\n"
            "Retired as the canonical FantasyGM Lab logo in favor of the "
            "FGL Arc Monogram. Kept for historical design reference only.\n"
            "Do not wire these assets into production surfaces.\n",
            encoding="utf-8",
        )

    print("Wrote FGL Arc Monogram brand assets to", BRAND)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
