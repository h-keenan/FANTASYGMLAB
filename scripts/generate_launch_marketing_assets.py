#!/usr/bin/env python3
"""Deterministic Founder Beta launch marketing compositions (Pillow).

Produces assets under assets/marketing/launch/ for external distribution.
Does not mount anything into the Streamlit app payload.

Usage:
  python scripts/generate_launch_marketing_assets.py
  python scripts/generate_launch_marketing_assets.py --capture   # also run harness screenshots
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402

from modules import share_card_renderer  # noqa: E402
from modules import share_recommendation_cards as share  # noqa: E402

_brand_spec = importlib.util.spec_from_file_location(
    "generate_brand_assets",
    ROOT / "scripts" / "generate_brand_assets.py",
)
_brand_gen = importlib.util.module_from_spec(_brand_spec)
assert _brand_spec.loader is not None
_brand_spec.loader.exec_module(_brand_gen)
draw_brand_mark = _brand_gen.draw_brand_mark

LAUNCH = ROOT / "assets" / "marketing" / "launch"
SCREENSHOTS = LAUNCH / "screenshots"
LEGACY = ROOT / "assets" / "marketing"
BRAND = ROOT / "assets" / "brand"

BG = (5, 6, 7)
SURFACE = (15, 17, 20)
SURFACE_RAISED = (27, 30, 35)
CYAN = (34, 211, 238)
WHITE = (248, 250, 252)
SLATE1 = (203, 213, 225)
SLATE2 = (148, 163, 184)
MUTED = (168, 173, 183)
EXPERIMENTAL = (139, 147, 255)

POSITIONING = (
    "League-aware recommendations for dynasty managers who want a clear next move."
)
SHORT_DESCRIPTOR = "Fantasy football front-office software for dynasty managers."
FOUNDER_BETA = "Founder Beta"
PRODUCT = "FantasyGM Lab"
DOMAIN = "fantasygmlab.com"
PRODUCT_URL = f"https://{DOMAIN}"

# Required deliverable filenames → dimensions
REQUIRED = {
    "hero-1200x630.png": (1200, 630),
    "hero-mobile-1080x1350.png": (1080, 1350),
    "trade-feature.png": (1080, 1350),
    "game-plan-feature.png": (1080, 1350),
    "decision-memory-feature.png": (1080, 1350),
    "youtube-short-1-cover.png": (1080, 1920),
    "youtube-short-2-cover.png": (1080, 1920),
    "youtube-short-3-cover.png": (1080, 1920),
    "free-vs-premium.png": (1080, 1350),
    "reddit-dashboard.png": (1080, 1350),
    "discord-share-card.png": (1080, 1350),
    "og-founder-beta-launch.png": (1200, 630),
    "qr-fantasygmlab.png": (512, 512),
}


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


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        box = draw.textbbox((0, 0), trial, font=font)
        if box[2] - box[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _load_source(*candidates: Path) -> Image.Image | None:
    for path in candidates:
        if path.exists():
            return Image.open(path).convert("RGB")
    return None


def _product_source(kind: str) -> Image.Image:
    """Prefer launch screenshots; fall back to landing marketing JPGs / share cards."""
    mapping = {
        "dashboard": (
            SCREENSHOTS / "dashboard-game-plan-390.png",
            SCREENSHOTS / "dashboard-game-plan-1440.png",
            LEGACY / "dashboard.jpg",
            LEGACY / "dashboard-desktop.jpg",
        ),
        "trade": (
            SCREENSHOTS / "trade-hub-390.png",
            SCREENSHOTS / "trade-review-390.png",
            LEGACY / "trade-hub.jpg",
            LEGACY / "trade-share.jpg",
        ),
        "waivers": (
            SCREENSHOTS / "waivers-390.png",
            LEGACY / "waivers.jpg",
            LEGACY / "waiver-share.jpg",
        ),
        "pqv": (
            SCREENSHOTS / "player-quick-view-390.png",
            LEGACY / "player-quick-view.jpg",
            LEGACY / "player-share.jpg",
        ),
        "memory": (
            SCREENSHOTS / "decision-memory-390.png",
            SCREENSHOTS / "what-changed-390.png",
            LEGACY / "decision-memory.jpg",
        ),
        "share": (
            LAUNCH / "share-trade-example.png",
            LEGACY / "trade-share.jpg",
        ),
    }
    image = _load_source(*mapping[kind])
    if image is None:
        # Solid placeholder with brand plate — never invent fake UI chrome.
        canvas = Image.new("RGB", (780, 1680), SURFACE)
        mark = draw_brand_mark(160)
        canvas.paste(mark, (310, 700), mark)
        return canvas
    return image


def _atmosphere(size: tuple[int, int]) -> Image.Image:
    w, h = size
    canvas = Image.new("RGB", size, BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 10, h), fill=CYAN)
    # Subtle vertical gradient band
    for y in range(h):
        t = y / max(h - 1, 1)
        shade = int(9 + t * 8)
        draw.line((10, y, w, y), fill=(shade, shade + 1, shade + 2))
    return canvas


def _fit_cover(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    x0, y0, x1, y1 = box
    tw, th = x1 - x0, y1 - y0
    src = image.convert("RGB")
    scale = max(tw / src.width, th / src.height)
    nw, nh = max(1, int(src.width * scale)), max(1, int(src.height * scale))
    src = src.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - tw) // 2)
    top = max(0, (nh - th) // 2)
    return src.crop((left, top, left + tw, top + th))


def _phone_frame(screenshot: Image.Image, *, frame_w: int, frame_h: int) -> Image.Image:
    frame = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)
    draw.rounded_rectangle((0, 0, frame_w - 1, frame_h - 1), radius=36, fill=(20, 22, 26))
    inset = 14
    inner = (inset, inset, frame_w - inset, frame_h - inset)
    draw.rounded_rectangle(inner, radius=28, fill=SURFACE)
    content = _fit_cover(
        screenshot,
        (inset + 4, inset + 4, frame_w - inset - 4, frame_h - inset - 4),
    )
    mask = Image.new("L", content.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, content.size[0] - 1, content.size[1] - 1), radius=24, fill=255
    )
    frame.paste(content, (inset + 4, inset + 4), mask)
    return frame


def _badge(draw, xy: tuple[int, int], text: str, font, *, color=CYAN) -> None:
    pad_x, pad_y = 14, 8
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    x, y = xy
    draw.rounded_rectangle(
        (x, y, x + tw + pad_x * 2, y + th + pad_y * 2),
        radius=8,
        fill=SURFACE_RAISED,
        outline=color,
        width=2,
    )
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=color)


def compose_hero_1200() -> Image.Image:
    canvas = _atmosphere((1200, 630))
    draw = ImageDraw.Draw(canvas)
    mark = draw_brand_mark(120)
    canvas.paste(mark, (56, 72), mark)
    title = _font(54, bold=True)
    body = _font(28)
    small = _font(22, bold=True)
    draw.text((200, 88), PRODUCT, font=title, fill=WHITE)
    _badge(draw, (200, 160), FOUNDER_BETA.upper(), small)
    lines = _wrap(draw, POSITIONING, body, 520)
    y = 230
    for line in lines:
        draw.text((56, y), line, font=body, fill=SLATE1)
        y += 38
    draw.text((56, 560), DOMAIN, font=_font(24), fill=CYAN)

    shot = _product_source("dashboard")
    phone = _phone_frame(shot, frame_w=420, frame_h=520)
    canvas.paste(phone, (720, 55), phone)
    return canvas


def compose_mobile_hero() -> Image.Image:
    canvas = _atmosphere((1080, 1350))
    draw = ImageDraw.Draw(canvas)
    mark = draw_brand_mark(112)
    canvas.paste(mark, (72, 72), mark)
    draw.text((210, 90), PRODUCT, font=_font(48, bold=True), fill=WHITE)
    _badge(draw, (210, 160), FOUNDER_BETA.upper(), _font(22, bold=True))
    y = 230
    for line in _wrap(draw, POSITIONING, _font(32), 920):
        draw.text((72, y), line, font=_font(32), fill=SLATE1)
        y += 44
    phone = _phone_frame(_product_source("dashboard"), frame_w=620, frame_h=820)
    canvas.paste(phone, (230, 420), phone)
    draw.text((72, 1280), DOMAIN, font=_font(28), fill=CYAN)
    return canvas


def compose_feature(
    *,
    title: str,
    support: str,
    kind: str,
    experimental: bool = False,
) -> Image.Image:
    canvas = _atmosphere((1080, 1350))
    draw = ImageDraw.Draw(canvas)
    mark = draw_brand_mark(96)
    canvas.paste(mark, (64, 56), mark)
    draw.text((184, 70), PRODUCT, font=_font(40, bold=True), fill=WHITE)
    label = f"{title}  [EXPERIMENTAL]" if experimental else title
    color = EXPERIMENTAL if experimental else CYAN
    _badge(draw, (64, 180), label, _font(24, bold=True), color=color)
    y = 260
    for line in _wrap(draw, support, _font(30), 940):
        draw.text((64, y), line, font=_font(30), fill=SLATE1)
        y += 42
    phone = _phone_frame(_product_source(kind), frame_w=640, frame_h=860)
    canvas.paste(phone, (220, 400), phone)
    draw.text((64, 1285), f"{FOUNDER_BETA} · {DOMAIN}", font=_font(24), fill=MUTED)
    return canvas


def compose_youtube_cover(
    *,
    hook: str,
    end_line: str,
    kind: str,
    experimental_note: str | None = None,
) -> Image.Image:
    canvas = _atmosphere((1080, 1920))
    draw = ImageDraw.Draw(canvas)
    mark = draw_brand_mark(120)
    canvas.paste(mark, (72, 80), mark)
    draw.text((220, 100), PRODUCT, font=_font(52, bold=True), fill=WHITE)
    _badge(draw, (220, 175), FOUNDER_BETA.upper(), _font(24, bold=True))
    y = 280
    for line in _wrap(draw, hook, _font(44, bold=True), 920):
        draw.text((72, y), line, font=_font(44, bold=True), fill=WHITE)
        y += 58
    if experimental_note:
        _badge(
            draw,
            (72, y + 12),
            experimental_note,
            _font(22, bold=True),
            color=EXPERIMENTAL,
        )
        y += 70
    phone = _phone_frame(_product_source(kind), frame_w=700, frame_h=980)
    canvas.paste(phone, (190, 620), phone)
    draw.text((72, 1750), end_line, font=_font(34, bold=True), fill=CYAN)
    draw.text((72, 1820), DOMAIN, font=_font(28), fill=MUTED)
    return canvas


def compose_free_vs_premium() -> Image.Image:
    canvas = _atmosphere((1080, 1350))
    draw = ImageDraw.Draw(canvas)
    mark = draw_brand_mark(96)
    canvas.paste(mark, (64, 48), mark)
    draw.text((184, 62), PRODUCT, font=_font(40, bold=True), fill=WHITE)
    draw.text((64, 170), "Free vs Premium", font=_font(44, bold=True), fill=WHITE)
    draw.text(
        (64, 230),
        "Free is useful. Premium is deeper — not a separate product.",
        font=_font(26),
        fill=SLATE1,
    )

    free_items = (
        "League-aware Today's Game Plan",
        "Limited decision inventory",
        "Player context & ranks",
        "Core trade & waiver workflows",
        "Session What Changed",
    )
    prem_items = (
        "Deeper recommendation inventory",
        "Full trade & waiver boards",
        "Advanced roster decision depth",
        "Decision Memory when enabled [EXPERIMENTAL]",
        "GM Targets when enabled [EXPERIMENTAL]",
    )

    def column(x: int, title: str, items: tuple[str, ...], accent) -> None:
        draw.rounded_rectangle((x, 320, x + 460, 1180), radius=20, fill=SURFACE, outline=accent, width=2)
        draw.text((x + 28, 350), title, font=_font(34, bold=True), fill=accent)
        yy = 430
        for item in items:
            for line in _wrap(draw, f"• {item}", _font(24), 400):
                draw.text((x + 28, yy), line, font=_font(24), fill=WHITE)
                yy += 36
            yy += 18

    column(64, "Free", free_items, CYAN)
    column(556, "Premium", prem_items, (250, 204, 21))
    draw.text(
        (64, 1230),
        f"Experimental lanes require flags + Premium where configured. {FOUNDER_BETA}.",
        font=_font(22),
        fill=MUTED,
    )
    return canvas


def compose_reddit_dashboard() -> Image.Image:
    return compose_feature(
        title="Today's Game Plan",
        support="A short stack of what to do next for this league — trades, waivers, and roster priorities.",
        kind="dashboard",
    )


def compose_discord_share() -> Image.Image:
    canvas = _atmosphere((1080, 1350))
    draw = ImageDraw.Draw(canvas)
    mark = draw_brand_mark(96)
    canvas.paste(mark, (64, 56), mark)
    draw.text((184, 70), PRODUCT, font=_font(40, bold=True), fill=WHITE)
    _badge(
        draw,
        (64, 180),
        "Share Recommendation  [EXPERIMENTAL]",
        _font(22, bold=True),
        color=EXPERIMENTAL,
    )
    y = 260
    for line in _wrap(
        draw,
        "Branded card for a trade, waiver, or player outlook you can already see.",
        _font(30),
        940,
    ):
        draw.text((64, y), line, font=_font(30), fill=SLATE1)
        y += 42

    card = _product_source("share")
    # Center share card without inventing UI
    max_w, max_h = 900, 780
    scale = min(max_w / card.width, max_h / card.height)
    nw, nh = max(1, int(card.width * scale)), max(1, int(card.height * scale))
    card = card.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (1080 - nw) // 2
    canvas.paste(card, (x, 420))
    draw.text((64, 1285), f"{FOUNDER_BETA} · {DOMAIN}", font=_font(24), fill=MUTED)
    return canvas


def compose_og_launch() -> Image.Image:
    """OG with FGL Arc Monogram + product name + positioning + Founder Beta (no tiny UI)."""
    canvas = Image.new("RGB", (1200, 630), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 12, 630), fill=CYAN)
    mark = draw_brand_mark(160)
    canvas.paste(mark, (72, 150), mark)
    draw.text((270, 160), PRODUCT, font=_font(60, bold=True), fill=WHITE)
    y = 250
    for line in _wrap(draw, POSITIONING, _font(30), 860):
        draw.text((270, y), line, font=_font(30), fill=SLATE1)
        y += 40
    draw.text((270, y + 20), FOUNDER_BETA.upper(), font=_font(26, bold=True), fill=SLATE2)
    draw.text((72, 560), DOMAIN, font=_font(28), fill=CYAN)
    return canvas


def generate_share_examples() -> None:
    share.clear_share_cache_for_tests()
    LAUNCH.mkdir(parents=True, exist_ok=True)
    examples = {
        "share-trade-example.png": share.build_trade_share_card(
            {
                "trade_gain": 314,
                "trade_confidence_label": "High",
                "reasoning_summary": "Acquire the ascending WR while sending replaceable depth.",
                "send_assets": [
                    {"name": "Depth WR", "position": "WR", "team": "CHI", "player_id": "101"},
                ],
                "receive_assets": [
                    {"name": "Alpha WR", "position": "WR", "team": "MIA", "player_id": "202"},
                ],
            }
        ),
        "share-waiver-example.png": share.build_waiver_share_card(
            {
                "name": "Breakout WR",
                "position": "WR",
                "team": "ATL",
                "player_id": "505",
                "opportunity_confidence": "High",
            },
            action="Add",
            reason="Immediate depth with a clear path to snaps.",
            position_rank=28,
            overall_rank=87,
            scoring_format="PPR",
        ),
        "share-player-example.png": share.build_player_share_card(
            display_name="Franchise RB",
            player_id="606",
            position="RB",
            team="SF",
            overall_rank=11,
            position_rank=3,
            scoring_format="PPR",
            narrative={
                "is_active_recommendation": True,
                "action": "Hold",
                "reason": "Workhorse role with durable weekly leverage.",
                "confidence_label": "High",
            },
        ),
    }
    for name, card in examples.items():
        png = share_card_renderer.render_share_card_png(card, portraits={})
        (LAUNCH / name).write_bytes(png)


def generate_qr(path: Path) -> None:
    try:
        import qrcode
    except ImportError:
        # Minimal fallback: branded tile with URL (no third-party QR dependency).
        canvas = Image.new("RGB", (512, 512), WHITE)
        draw = ImageDraw.Draw(canvas)
        mark = draw_brand_mark(128, light=True)
        canvas.paste(mark, (192, 120), mark)
        draw.text((70, 300), PRODUCT_URL, font=_font(22, bold=True), fill=(15, 23, 42))
        draw.text((120, 360), "Scan unavailable — use URL", font=_font(18), fill=(100, 116, 139))
        canvas.save(path)
        print("qrcode package missing; wrote URL fallback tile:", path.name)
        return

    qr = qrcode.QRCode(version=3, box_size=10, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(PRODUCT_URL)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((512, 512), Image.Resampling.NEAREST)
    # Overlay small FGL Arc Monogram in quiet zone center (still scannable with EC-M)
    mark = draw_brand_mark(72, light=True)
    img.paste(mark, (220, 220), mark)
    img.save(path)


def write_readme() -> None:
    lines = [
        "# Founder Beta launch assets",
        "",
        "External distribution kit for YouTube Shorts, Reddit, Discord, X, DMs, and OG previews.",
        "Canonical brand: FantasyGM Lab FGL Arc Monogram.",
        "",
        "**These files are not loaded by the authenticated Streamlit app.**",
        "",
        "## Inventory",
        "",
        "| File | Size | Use |",
        "| --- | --- | --- |",
    ]
    for name, (w, h) in REQUIRED.items():
        lines.append(f"| `{name}` | {w}×{h} | External launch |")
    lines += [
        "| `share-*-example.png` | card | Experimental Share Recommendation examples |",
        "| `screenshots/*-390.png` | 390-wide | Clean product captures |",
        "| `screenshots/*-1440.png` | 1440-wide | Clean product captures |",
        "",
        "## Regenerate",
        "",
        "```bash",
        "python scripts/generate_launch_marketing_assets.py",
        "python scripts/generate_launch_marketing_assets.py --capture",
        "```",
        "",
        "Optional QR dependency: `pip install qrcode[pil]`",
        "",
        "See `docs/founder-beta-launch-marketing-kit.md` for copy and usage rules.",
        "",
    ]
    (LAUNCH / "README.md").write_text("\n".join(lines), encoding="utf-8")


def validate_dimensions() -> list[str]:
    errors: list[str] = []
    for name, expected in REQUIRED.items():
        path = LAUNCH / name
        if not path.exists():
            errors.append(f"missing {name}")
            continue
        with Image.open(path) as image:
            if image.size != expected:
                errors.append(f"{name} size {image.size} != {expected}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Run harness screenshot capture before composing.",
    )
    parser.add_argument("--skip-qr", action="store_true")
    args = parser.parse_args()

    LAUNCH.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    if args.capture:
        cap_spec = importlib.util.spec_from_file_location(
            "capture_launch_screenshots",
            ROOT / "scripts" / "capture_launch_screenshots.py",
        )
        cap_mod = importlib.util.module_from_spec(cap_spec)
        assert cap_spec.loader is not None
        cap_spec.loader.exec_module(cap_mod)
        cap_mod.capture()

    generate_share_examples()

    compositions = {
        "hero-1200x630.png": compose_hero_1200,
        "hero-mobile-1080x1350.png": compose_mobile_hero,
        "trade-feature.png": lambda: compose_feature(
            title="Trade Hub",
            support="Generated trade paths with package review, partner context, and value change.",
            kind="trade",
        ),
        "game-plan-feature.png": lambda: compose_feature(
            title="Today's Game Plan",
            support="A short stack of what to do next — trades, waivers, and roster priorities.",
            kind="dashboard",
        ),
        "decision-memory-feature.png": lambda: compose_feature(
            title="Decision Memory / GM Targets",
            support="Cross-session priority history and saved players to monitor — when enabled.",
            kind="memory",
            experimental=True,
        ),
        "youtube-short-1-cover.png": lambda: compose_youtube_cover(
            hook="Stop checking five different fantasy sites just to decide your next move.",
            end_line="FantasyGM Lab — Founder Beta",
            kind="dashboard",
        ),
        "youtube-short-2-cover.png": lambda: compose_youtube_cover(
            hook="Would you make this dynasty trade?",
            end_line="Try it with your league.",
            kind="trade",
        ),
        "youtube-short-3-cover.png": lambda: compose_youtube_cover(
            hook="Your dynasty advice shouldn't reset every time you log in.",
            end_line="FantasyGM Lab — Founder Beta",
            kind="memory",
            experimental_note="EXPERIMENTAL — when enabled",
        ),
        "free-vs-premium.png": compose_free_vs_premium,
        "reddit-dashboard.png": compose_reddit_dashboard,
        "discord-share-card.png": compose_discord_share,
        "og-founder-beta-launch.png": compose_og_launch,
    }

    for name, builder in compositions.items():
        image = builder()
        path = LAUNCH / name
        image.save(path, format="PNG", optimize=True)
        print("wrote", path.relative_to(ROOT), image.size)

    if not args.skip_qr:
        generate_qr(LAUNCH / "qr-fantasygmlab.png")
        print("wrote", (LAUNCH / "qr-fantasygmlab.png").relative_to(ROOT))

    # Keep production OG aligned with launch positioning (no tiny UI screenshot).
    og = compose_og_launch()
    og.save(BRAND / "og-founder-beta.png", format="PNG", optimize=True)
    print("updated", (BRAND / "og-founder-beta.png").relative_to(ROOT))

    write_readme()
    errors = validate_dimensions()
    if errors:
        print("VALIDATION ERRORS:", file=sys.stderr)
        for err in errors:
            print(" -", err, file=sys.stderr)
        return 1
    print("Validated", len(REQUIRED), "launch assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
