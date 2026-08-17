"""Deterministic Pillow renderer for FantasyGM Lab Share Recommendation cards.

Content-driven vertical flow. One canonical PNG path. Portrait aspect ratio is
always preserved (contain-fit inside a square box).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

from modules import brand_identity
from modules import share_card_qr
from modules import share_recommendation_cards as share


# FantasyGM Lab executive palette (matches design tokens, not a new system).
BG = (5, 6, 7)
SURFACE = (15, 17, 20)
SURFACE_RAISED = (27, 30, 35)
PORTRAIT_BG = (55, 62, 72)
TEXT = (236, 238, 242)
MUTED = (156, 163, 175)
ACCENT = (56, 189, 210)
POSITIVE = (74, 222, 128)
NEGATIVE = (248, 113, 113)
BORDER = (42, 46, 54)
BAR_TRACK = (32, 36, 42)

RENDER_VERSION = share.RENDER_VERSION
MAX_VISIBLE_ASSETS = 3
TIER_SIMPLE = "simple"
TIER_STANDARD = "standard"
TIER_DENSE = "dense"

_FONT_CACHE: dict[tuple[int, bool], object] = {}

# Keep common punctuation; drop emoji / pictographs that rasterize as tofu.
_KEEP_SYMBOLS = frozenset("•·→←—–★☆+±×÷")
_EMOJI_RANGES = (
    (0x1F000, 0x1FAFF),
    (0x1F1E6, 0x1F1FF),
    (0x2600, 0x27BF),
    (0xFE00, 0xFE0F),
    (0x200D, 0x200D),
    (0x20E3, 0x20E3),
    (0xE0020, 0xE007F),
)


def share_display_text(text: object) -> str:
    """PNG-only glyph safety. Does not mutate stored team or player names."""

    raw = str(text or "")
    if not raw:
        return ""
    chars: list[str] = []
    for ch in raw:
        code = ord(ch)
        if ch in "\n\r\t":
            chars.append(" ")
            continue
        category = unicodedata.category(ch)
        if category in {"Cc", "Cf", "Cs", "Co", "Cn"}:
            continue
        if ch in _KEEP_SYMBOLS:
            chars.append(ch)
            continue
        if any(start <= code <= end for start, end in _EMOJI_RANGES):
            continue
        if category.startswith("S") and code > 0xFF:
            continue
        chars.append(ch)
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def _t(text: object) -> str:
    return share_display_text(text)


def _require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Pillow is required for Share Recommendation cards. "
            "Install pillow via requirements.txt."
        ) from exc
    return Image, ImageDraw, ImageFont


def _font(ImageFont, size: int, *, bold: bool = False):
    key = (int(size), bool(bold))
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached
    candidates = []
    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/macos/Inter-SemiBold.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            ]
        )
    candidates.extend(
        [
            "/usr/share/fonts/truetype/macos/Inter-Medium.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    )
    font = None
    for path in candidates:
        try:
            font = ImageFont.truetype(path, size=size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def _text_width(draw, text: str, font) -> int:
    box = draw.textbbox((0, 0), _t(text), font=font)
    return int(box[2] - box[0])


def _text_height(draw, text: str, font) -> int:
    box = draw.textbbox((0, 0), _t(text), font=font)
    return max(1, int(box[3] - box[1]))


def _wrap(draw, text: str, font, max_width: int, *, max_lines: int | None = None) -> list[str]:
    words = _t(text).split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if _text_width(draw, trial, font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    if max_lines is None:
        return lines
    return lines[: max(1, int(max_lines))]


def _rounded_rect(draw, xy, radius: int, fill) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def value_edge_bar_geometry(
    *,
    acquire: int | None,
    send: int | None,
    delta: int,
    max_px: int,
) -> dict[str, int | str | bool]:
    """One bipolar bar. Center is even; fill is the value edge, not two side bars.

    When both side totals exist, fill is |delta| / max(side, |delta|) of half the
    track — a 1% edge stays a 1% fill. When totals are absent (Trade Analyzer),
    the numeric VALUE EDGE remains the source of truth and the bar is a modest
    directional cue only.
    """

    half = max(8, int(max_px) // 2)
    signed = int(delta or 0)
    if signed > 0:
        direction = "receive"
    elif signed < 0:
        direction = "send"
    else:
        direction = "even"
    quantified = acquire is not None and send is not None
    if direction == "even":
        return {"half": half, "fill": 0, "direction": direction, "quantified": quantified}
    if quantified:
        peak = max(int(acquire or 0), int(send or 0), abs(signed), 1)
        fill = int(round(half * abs(signed) / peak))
        fill = min(half, max(fill, 4))
    else:
        fill = max(8, half // 4)
    return {"half": half, "fill": fill, "direction": direction, "quantified": quantified}


def card_value_delta(card: share.ShareRecommendationCard) -> int:
    """Prefer canonical side totals; otherwise parse the already-owned VALUE EDGE."""

    if card.acquire_total is not None and card.send_total is not None:
        return int(card.acquire_total) - int(card.send_total)
    text = str(card.value_change or "").replace(",", "").replace("Even", "0").strip()
    if not text:
        return 0
    try:
        return int(round(float(text)))
    except ValueError:
        return 0


def phone_display_png(png: bytes, display_width: int) -> bytes:
    """Fit-to-screen raster used to judge composition at iPhone display widths."""

    Image, _, _ = _require_pillow()
    image = Image.open(BytesIO(png)).convert("RGB")
    width = max(1, int(display_width))
    if image.width == width:
        return png
    height = int(round(image.height * (width / image.width)))
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
    fitted = image.resize((width, height), resample)
    buffer = BytesIO()
    fitted.save(buffer, format="PNG", optimize=True, compress_level=6)
    return buffer.getvalue()


def _high_res_mark(Image, size: int):
    """Prefer a large raster mark so the logo stays sharp at 2x."""

    candidates = []
    compact = brand_identity.asset_path("brand_compact_png")
    if compact.exists():
        candidates.append(compact)
    share_mark = brand_identity.asset_path("share_card_mark")
    if share_mark.exists():
        candidates.append(share_mark)
    raw = b""
    for path in candidates:
        try:
            raw = path.read_bytes()
            if len(raw) > 400:
                break
        except OSError:
            continue
    if not raw:
        raw = brand_identity.share_card_mark_png_bytes()
    if not raw:
        return None
    mark = Image.open(BytesIO(raw)).convert("RGBA")
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
    return mark.resize((size, size), resample)


VISIBLE_ALPHA_MIN = 20
OPAQUE_BG_DELTA = 28
CROP_MIN_AREA_RATIO = 0.04
CROP_MAX_AREA_RATIO = 0.992


def _channel_abs_diff(channel, value: int):
    value = max(0, min(255, int(value)))
    return channel.point(lambda pixel, pivot=value: abs(int(pixel) - pivot))


def _corner_background_rgb(image) -> tuple[int, int, int]:
    sample = image.convert("RGB")
    width, height = sample.size
    pixels = sample.load()
    coords = (
        (0, 0),
        (max(0, width - 1), 0),
        (0, max(0, height - 1)),
        (max(0, width - 1), max(0, height - 1)),
        (width // 2, 0),
        (width // 2, max(0, height - 1)),
    )
    totals = [0, 0, 0]
    count = 0
    for x, y in coords:
        color = pixels[x, y]
        totals[0] += int(color[0])
        totals[1] += int(color[1])
        totals[2] += int(color[2])
        count += 1
    if not count:
        return (0, 0, 0)
    return (totals[0] // count, totals[1] // count, totals[2] // count)


def _flood_fill_content_bbox(image, background: tuple[int, int, int]):
    """Treat corner-connected near-background pixels as padding."""

    try:
        from PIL import ImageDraw
    except Exception:
        return None
    work = image.convert("RGB")
    filled = work.copy()
    sentinel = (254, 0, 253)
    if background == sentinel:
        sentinel = (253, 0, 254)
    width, height = filled.size
    kwargs = {"thresh": OPAQUE_BG_DELTA}
    try:
        ImageDraw.floodfill(filled, (0, 0), sentinel, **kwargs)
    except TypeError:
        kwargs = {}
        ImageDraw.floodfill(filled, (0, 0), sentinel)
    for seed in (
        (max(0, width - 1), 0),
        (0, max(0, height - 1)),
        (max(0, width - 1), max(0, height - 1)),
    ):
        ImageDraw.floodfill(filled, seed, sentinel, **kwargs)
    pixels = filled.load()
    left, top, right, bottom = width, height, 0, 0
    found = False
    for y in range(height):
        for x in range(width):
            if pixels[x, y] != sentinel:
                found = True
                if x < left:
                    left = x
                if y < top:
                    top = y
                if x > right:
                    right = x
                if y > bottom:
                    bottom = y
    if not found:
        return None
    return (left, top, right + 1, bottom + 1)


def visible_content_bbox(image, *, fill_rgb: tuple[int, int, int] | None = None):
    """Return the bounding box of visible player geometry, or None."""

    try:
        from PIL import ImageChops
    except Exception:
        return None
    try:
        work = image.convert("RGBA") if getattr(image, "mode", "") != "RGBA" else image
        alpha = work.getchannel("A")
        extrema = alpha.getextrema()
        if extrema and extrema[0] < 250:
            mask = alpha.point(
                lambda pixel: 255 if int(pixel) > VISIBLE_ALPHA_MIN else 0
            )
            return mask.getbbox()
        background = fill_rgb if fill_rgb is not None else _corner_background_rgb(work)
        if fill_rgb is None:
            flooded = _flood_fill_content_bbox(work, background)
            if flooded:
                return flooded
        red, green, blue, _alpha = work.split()
        delta = ImageChops.lighter(
            ImageChops.lighter(
                _channel_abs_diff(red, background[0]),
                _channel_abs_diff(green, background[1]),
            ),
            _channel_abs_diff(blue, background[2]),
        )
        mask = delta.point(lambda pixel: 255 if int(pixel) > OPAQUE_BG_DELTA else 0)
        return mask.getbbox()
    except Exception:
        return None


def normalize_player_cutout(image):
    """Crop asymmetric padding while preserving aspect ratio of remaining pixels."""

    try:
        work = image.convert("RGBA") if getattr(image, "mode", "") != "RGBA" else image
        bbox = visible_content_bbox(work)
        if not bbox:
            return work
        left, top, right, bottom = bbox
        width = max(1, right - left)
        height = max(1, bottom - top)
        area = max(1, work.width * work.height)
        ratio = (width * height) / area
        if ratio < CROP_MIN_AREA_RATIO or ratio > CROP_MAX_AREA_RATIO:
            return work
        pad = 1
        crop = (
            max(0, left - pad),
            max(0, top - pad),
            min(work.width, right + pad),
            min(work.height, bottom + pad),
        )
        return work.crop(crop)
    except Exception:
        return image


def trim_transparent_bounds(image):
    """Crop transparent or near-background padding. Falls back to the source image."""

    return normalize_player_cutout(image)


def normalize_player_cutout_for_box(Image, raw: bytes | None, box_w: int, box_h: int):
    """Canonical portrait owner: trim visible geometry, then contain-fit the box."""

    return fit_portrait_into_box(Image, raw, box_w, box_h)


def fit_portrait_into_box(Image, raw: bytes | None, box_w: int, box_h: int):
    """Aspect-preserving contain-fit. Never scales X and Y independently.

    Visible player geometry is cropped first. The remaining cutout is scaled
    uniformly, centered horizontally, and bottom-aligned when taller than wide.
    """

    slot = Image.new("RGBA", (box_w, box_h), PORTRAIT_BG + (255,))
    meta = {
        "source_mode": "",
        "source_width": 0,
        "source_height": 0,
        "trimmed_width": 0,
        "trimmed_height": 0,
        "fitted_width": 0,
        "fitted_height": 0,
        "scale": 0.0,
        "algorithm": "contain",
        "paste_x": 0,
        "paste_y": 0,
    }
    if not raw:
        from PIL import ImageDraw as _Draw

        d = _Draw.Draw(slot)
        d.ellipse((box_w * 0.28, box_h * 0.18, box_w * 0.72, box_h * 0.55), fill=(90, 98, 110, 255))
        d.ellipse((box_w * 0.18, box_h * 0.52, box_w * 0.82, box_h * 1.15), fill=(90, 98, 110, 255))
        return slot.convert("RGB"), meta
    try:
        portrait = Image.open(BytesIO(raw))
        meta["source_mode"] = str(portrait.mode)
        meta["source_width"] = int(portrait.width)
        meta["source_height"] = int(portrait.height)
        if portrait.mode not in {"RGB", "RGBA"}:
            portrait = portrait.convert("RGBA")
        elif portrait.mode == "RGB":
            portrait = portrait.convert("RGBA")
        portrait = normalize_player_cutout(portrait)
        meta["trimmed_width"] = int(portrait.width)
        meta["trimmed_height"] = int(portrait.height)
        if portrait.width <= 0 or portrait.height <= 0:
            return slot.convert("RGB"), meta
        scale = min(box_w / portrait.width, box_h / portrait.height)
        nw = max(1, int(round(portrait.width * scale)))
        nh = max(1, int(round(portrait.height * scale)))
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
        fitted = portrait.resize((nw, nh), resample)
        meta["fitted_width"] = nw
        meta["fitted_height"] = nh
        meta["scale"] = float(scale)
        x = (box_w - nw) // 2
        if portrait.height >= portrait.width:
            y = box_h - nh
        else:
            y = (box_h - nh) // 2
        meta["paste_x"] = int(x)
        meta["paste_y"] = int(y)
        slot.paste(fitted, (x, y), fitted)
    except Exception:
        pass
    return slot.convert("RGB"), meta


def portrait_visible_horizontal_center(slot, *, fill_rgb: tuple[int, int, int] = PORTRAIT_BG) -> float | None:
    """Horizontal center of non-background pixels inside a composited portrait slot."""

    bbox = visible_content_bbox(slot, fill_rgb=fill_rgb)
    if not bbox:
        return None
    left, _top, right, _bottom = bbox
    return (left + right) / 2.0


def _paste_portrait(Image, canvas, raw: bytes | None, box: tuple[int, int, int, int]) -> dict:
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    slot, meta = fit_portrait_into_box(Image, raw, w, h)
    mask = Image.new("L", (w, h), 0)
    from PIL import ImageDraw as _Draw2

    _Draw2.Draw(mask).rounded_rectangle((0, 0, w, h), radius=max(12, w // 8), fill=255)
    canvas.paste(slot, (x0, y0), mask)
    return meta


def _load_portraits(card: share.ShareRecommendationCard) -> dict[str, bytes | None]:
    out: dict[str, bytes | None] = {}
    for line in list(card.acquire_lines) + list(card.send_lines):
        if line.player_id and line.player_id not in out:
            out[line.player_id] = share.fetch_portrait_bytes(line.player_id)
    return out


def _cache_key(card: share.ShareRecommendationCard, width: int, height: int) -> str:
    return f"{card.fingerprint}:{RENDER_VERSION}:{width}x{height}:{share_card_qr.RENDER_VERSION}"


def layout_tier_for_card(card: share.ShareRecommendationCard) -> str:
    send_n = min(MAX_VISIBLE_ASSETS, len(list(card.send_lines or ())))
    get_n = min(MAX_VISIBLE_ASSETS, len(list(card.acquire_lines or ())))
    if card.card_type != share.CARD_TYPE_TRADE:
        return TIER_SIMPLE
    peak = max(send_n, get_n, 1)
    if peak <= 1:
        return TIER_SIMPLE
    if peak == 2 and min(send_n, get_n) <= 1:
        return TIER_STANDARD
    return TIER_DENSE


@dataclass(frozen=True)
class LayoutTokens:
    tier: str
    portrait: int
    title_size: int
    name_size: int
    section_gap: int
    asset_gap: int
    sep_slot: int
    name_line: int
    meta_line: int
    pick_chip: int


def layout_tokens(s: int, tier: str) -> LayoutTokens:
    if tier == TIER_DENSE:
        return LayoutTokens(
            tier=tier,
            portrait=72 * s,
            title_size=34 * s,
            name_size=30 * s,
            section_gap=16 * s,
            asset_gap=10 * s,
            sep_slot=24 * s,
            name_line=32 * s,
            meta_line=22 * s,
            pick_chip=40 * s,
        )
    if tier == TIER_STANDARD:
        return LayoutTokens(
            tier=tier,
            portrait=80 * s,
            title_size=36 * s,
            name_size=30 * s,
            section_gap=18 * s,
            asset_gap=12 * s,
            sep_slot=26 * s,
            name_line=34 * s,
            meta_line=24 * s,
            pick_chip=42 * s,
        )
    return LayoutTokens(
        tier=TIER_SIMPLE,
        portrait=88 * s,
        title_size=38 * s,
        name_size=32 * s,
        section_gap=20 * s,
        asset_gap=12 * s,
        sep_slot=28 * s,
        name_line=36 * s,
        meta_line=24 * s,
        pick_chip=44 * s,
    )


def _visible_asset_lines(lines) -> list:
    return list(lines)[:MAX_VISIBLE_ASSETS]


def _asset_block_height(draw, line, tokens: LayoutTokens, name_font, meta_font, col_w: int) -> int:
    if getattr(line, "kind", "player") == "player":
        text_w = max(40, col_w - tokens.portrait - 16)
        names = _untruncated_name_lines(draw, line.label, name_font, text_w)
        text_h = tokens.name_line * len(names)
        if getattr(line, "subtitle", ""):
            text_h += tokens.meta_line
        return max(tokens.portrait, text_h) + tokens.asset_gap
    pick_lines = _untruncated_name_lines(draw, line.label, meta_font, max(40, col_w - 24))
    chip = max(tokens.pick_chip, tokens.meta_line * len(pick_lines) + 16)
    return chip + 8


def _matchup_column_height(draw, lines, tokens: LayoutTokens, name_font, meta_font, col_w: int) -> int:
    extra = tokens.name_line
    visible = _visible_asset_lines(lines)
    for index, line in enumerate(visible):
        if index:
            extra += tokens.sep_slot
        extra += _asset_block_height(draw, line, tokens, name_font, meta_font, col_w)
    overflow = max(0, len(list(lines)) - len(visible))
    if overflow:
        extra += 28
    return extra


def _why_lines(draw, card, body_font, max_w: int) -> list[str]:
    text = card.reason or "See FantasyGM Lab for the full analysis."
    return _wrap(draw, text, body_font, max_w, max_lines=4)


def render_share_card_png(
    card: share.ShareRecommendationCard,
    *,
    width: int = share.SHARE_WIDTH,
    height: int | None = None,
    portraits: dict[str, bytes | None] | None = None,
) -> bytes:
    """Render a share PNG. Uses cache when fingerprint matches.

    ``height`` is accepted for API compatibility. Canvas height is content-driven
    and clamped to SHARE_HEIGHT_MIN / SHARE_HEIGHT_MAX. The footer is never pinned
    to a global Y.
    """

    if not card.is_shareable:
        raise ValueError(card.decline_reason or "Recommendation is not shareable.")

    Image, ImageDraw, ImageFont = _require_pillow()
    portraits = portraits if portraits is not None else _load_portraits(card)
    s = max(1, int(round(width / 1080)))
    tier = layout_tier_for_card(card)
    tokens = layout_tokens(s, tier)
    pad = 36 * s

    probe = Image.new("RGB", (width, 8), BG)
    probe_draw = ImageDraw.Draw(probe)
    brand_font = _font(ImageFont, 36 * s, bold=True)
    kicker_font = _font(ImageFont, 22 * s, bold=True)
    title_font = _font(ImageFont, tokens.title_size, bold=True)
    hero_font = _font(ImageFont, tokens.name_size, bold=True)
    section_font = _font(ImageFont, 22 * s, bold=True)
    body_font = _font(ImageFont, 30 * s)
    meta_font = _font(ImageFont, 20 * s, bold=True)
    footer_font = _font(ImageFont, 22 * s)
    value_font = _font(ImageFont, 28 * s, bold=True)
    edge_font = _font(ImageFont, 52 * s, bold=True)

    rec_title = _t((card.action or card.title or "Recommendation").replace(" PLUS ", " + "))
    show_title = card.card_type != share.CARD_TYPE_TRADE
    title_lines = _wrap(probe_draw, rec_title.upper(), title_font, width - pad * 2, max_lines=2) if show_title else []
    why_lines = _why_lines(probe_draw, card, body_font, width - pad * 2)

    y = 24 * s
    header_h = 84 * s
    title_h = (44 * s * max(1, len(title_lines)) + 8 * s) if title_lines else 0
    y_after_title = y + header_h + title_h
    if _t(card.context_line):
        y_after_title += 28 * s

    if card.card_type == share.CARD_TYPE_TRADE:
        gap = 28 * s
        col_w = (width - pad * 2 - gap) // 2
        inner_w = col_w - 16 * s
        give_h = _matchup_column_height(
            probe_draw, card.send_lines, tokens, hero_font, meta_font, inner_w
        )
        get_h = _matchup_column_height(
            probe_draw, card.acquire_lines, tokens, hero_font, meta_font, inner_w
        )
        matchup_h = max(give_h, get_h)
        value_h = 80 * s
        body_h = matchup_h + tokens.section_gap + value_h
    else:
        matchup_h = 0
        body_h = tokens.portrait + 180 * s

    why_h = 28 * s + 32 * s * max(1, len(why_lines))
    footer_h = 64 * s + 12 * s
    natural = (
        y_after_title
        + body_h
        + tokens.section_gap
        + why_h
        + tokens.section_gap
        + footer_h
        + pad
    )
    canvas_h = min(share.SHARE_HEIGHT_MAX, max(share.SHARE_HEIGHT_MIN, int(natural)))
    if height is not None and int(height) == canvas_h:
        canvas_h = int(height)

    key = _cache_key(card, width, canvas_h) if card.fingerprint else ""
    cached = share.cache_get(key) if key else None
    if cached:
        return cached

    canvas = Image.new("RGB", (width, canvas_h), BG)
    draw = ImageDraw.Draw(canvas)

    mark_size = 52 * s
    mark_img = _high_res_mark(Image, mark_size)
    if mark_img is not None:
        canvas.paste(mark_img, (pad, y), mark_img)
        text_x = pad + mark_size + 14 * s
    else:
        draw.text((pad, y + 8 * s), brand_identity.PRODUCT_MARK, font=hero_font, fill=ACCENT)
        text_x = pad + _text_width(draw, brand_identity.PRODUCT_MARK, hero_font) + 14 * s
    draw.text((text_x, y + 4 * s), _t(brand_identity.PRODUCT_NAME), font=brand_font, fill=TEXT)
    if card.source_surface == "trade_analyzer":
        kicker = "TRADE ANALYSIS"
    elif card.card_type == share.CARD_TYPE_TRADE:
        kicker = "TRADE"
    else:
        kicker = "RECOMMENDATION"
    draw.text((text_x, y + 42 * s), kicker, font=kicker_font, fill=ACCENT)
    y += header_h
    context = _t(card.context_line)
    if context:
        draw.text((pad, y - 8 * s), context, font=meta_font, fill=MUTED)
        y += 28 * s

    for line in title_lines:
        draw.text((pad, y), _t(line), font=title_font, fill=TEXT)
        y += 44 * s
    if title_lines:
        y += 8 * s

    if card.card_type == share.CARD_TYPE_TRADE:
        y = _render_trade(
            Image,
            draw,
            canvas,
            card,
            portraits,
            y,
            pad,
            width,
            s,
            tokens,
            hero_font,
            section_font,
            meta_font,
            value_font,
            edge_font,
        )
    else:
        y = _render_single_player(
            Image,
            draw,
            canvas,
            card,
            portraits,
            y,
            pad,
            width,
            s,
            tokens,
            hero_font,
            section_font,
            body_font,
            meta_font,
        )

    y += tokens.section_gap
    draw.text((pad, y), "WHY", font=section_font, fill=MUTED)
    y += 28 * s
    for line in why_lines:
        draw.text((pad, y), _t(line), font=body_font, fill=TEXT)
        y += 32 * s

    y += tokens.section_gap
    _draw_brand_footer(Image, draw, canvas, card, y, width, pad, s, footer_font, brand_font)

    buffer = BytesIO()
    canvas.save(buffer, format="PNG", optimize=True, compress_level=4)
    payload = buffer.getvalue()
    if key:
        share.cache_put(key, payload)
    return payload


def describe_share_layout(card: share.ShareRecommendationCard, *, width: int = share.SHARE_WIDTH) -> dict:
    """Diagnostics for tests/artifacts — no PII beyond already-public labels."""

    Image, ImageDraw, ImageFont = _require_pillow()
    s = max(1, int(round(width / 1080)))
    tier = layout_tier_for_card(card)
    tokens = layout_tokens(s, tier)
    pad = 36 * s
    probe = Image.new("RGB", (width, 8), BG)
    draw = ImageDraw.Draw(probe)
    title_font = _font(ImageFont, tokens.title_size, bold=True)
    hero_font = _font(ImageFont, tokens.name_size, bold=True)
    meta_font = _font(ImageFont, 20 * s, bold=True)
    body_font = _font(ImageFont, 30 * s)
    rec_title = _t((card.action or card.title or "Recommendation").replace(" PLUS ", " + "))
    show_title = card.card_type != share.CARD_TYPE_TRADE
    title_lines = _wrap(draw, rec_title.upper(), title_font, width - pad * 2, max_lines=2) if show_title else []
    why_lines = _why_lines(draw, card, body_font, width - pad * 2)
    gap = 28 * s
    col_w = (width - pad * 2 - gap) // 2
    inner_w = col_w - 16 * s
    give_h = _matchup_column_height(draw, card.send_lines, tokens, hero_font, meta_font, inner_w)
    get_h = _matchup_column_height(draw, card.acquire_lines, tokens, hero_font, meta_font, inner_w)
    natural = 24 * s + 84 * s
    if _t(card.context_line):
        natural += 28 * s
    natural += 44 * s * max(0, len(title_lines)) + (8 * s if title_lines else 0)
    if card.card_type == share.CARD_TYPE_TRADE:
        natural += max(give_h, get_h) + tokens.section_gap + 80 * s
    else:
        natural += tokens.portrait + 180 * s
    natural += tokens.section_gap + 28 * s + 32 * s * max(1, len(why_lines))
    natural += tokens.section_gap + 64 * s + 12 * s + pad
    return {
        "tier": tier,
        "width": width,
        "natural_height": int(natural),
        "card_height": min(share.SHARE_HEIGHT_MAX, max(share.SHARE_HEIGHT_MIN, int(natural))),
        "portrait": tokens.portrait,
        "send_stack_height": give_h,
        "acquire_stack_height": get_h,
        "matchup_height": max(give_h, get_h),
        "why_lines": len(why_lines),
        "section_gap": tokens.section_gap,
        "sep_slot": tokens.sep_slot,
    }


def _draw_brand_footer(Image, draw, canvas, card, y, width, pad, s, footer_font, brand_font):
    qr_size = 64 * s
    qr_bytes = share_card_qr.share_qr_png_bytes(box_size=max(4, 3 * s), border=4)
    qr_img = Image.open(BytesIO(qr_bytes)).convert("RGB")
    resample = getattr(getattr(Image, "Resampling", Image), "NEAREST", Image.NEAREST)
    qr_img = qr_img.resize((qr_size, qr_size), resample)
    qr_x = pad
    qr_y = y
    plate = (qr_x - 4 * s, qr_y - 4 * s, qr_x + qr_size + 4 * s, qr_y + qr_size + 4 * s)
    _rounded_rect(draw, plate, 8 * s, (255, 255, 255))
    canvas.paste(qr_img, (qr_x, qr_y))
    copy_x = qr_x + qr_size + 16 * s
    draw.text((copy_x, qr_y + 8 * s), _t(brand_identity.PRODUCT_DOMAIN), font=footer_font, fill=MUTED)
    draw.text((copy_x, qr_y + 34 * s), _t(share_card_qr.QR_LABEL), font=footer_font, fill=MUTED)
    return y + qr_size + 8 * s


def _render_trade(
    Image,
    draw,
    canvas,
    card,
    portraits,
    y,
    pad,
    width,
    s,
    tokens: LayoutTokens,
    hero_font,
    section_font,
    meta_font,
    value_font,
    edge_font,
):
    gap = 28 * s
    col_w = (width - pad * 2 - gap) // 2
    left_x = pad
    right_x = pad + col_w + gap
    inner_w = col_w - 16 * s
    portrait = min(tokens.portrait, max(64 * s, inner_w // 3))
    tokens = LayoutTokens(**{**tokens.__dict__, "portrait": portrait})
    give_h = _matchup_column_height(draw, card.send_lines, tokens, hero_font, meta_font, inner_w)
    get_h = _matchup_column_height(draw, card.acquire_lines, tokens, hero_font, meta_font, inner_w)
    col_h = max(give_h, get_h)
    draw.line((left_x, y, left_x + 10 * s, y + col_h), fill=NEGATIVE, width=max(4, 3 * s))
    draw.line((right_x, y, right_x + 10 * s, y + col_h), fill=POSITIVE, width=max(4, 3 * s))
    _render_matchup_column(
        Image,
        draw,
        canvas,
        title="YOU GIVE",
        total=card.send_total,
        lines=card.send_lines,
        portraits=portraits,
        x=left_x + 16 * s,
        y=y,
        col_w=inner_w,
        s=s,
        tokens=tokens,
        section_font=section_font,
        hero_font=hero_font,
        meta_font=meta_font,
        value_font=value_font,
        accent=NEGATIVE,
    )
    arrow = "→"
    draw.text(
        (left_x + col_w + (gap - _text_width(draw, arrow, hero_font)) // 2, y + col_h // 2 - 24 * s),
        arrow,
        font=hero_font,
        fill=ACCENT,
    )
    _render_matchup_column(
        Image,
        draw,
        canvas,
        title="YOU GET",
        total=card.acquire_total,
        lines=card.acquire_lines,
        portraits=portraits,
        x=right_x + 16 * s,
        y=y,
        col_w=inner_w,
        s=s,
        tokens=tokens,
        section_font=section_font,
        hero_font=hero_font,
        meta_font=meta_font,
        value_font=value_font,
        accent=POSITIVE,
    )
    y += col_h + tokens.section_gap
    return _render_value_edge(
        draw,
        card,
        y,
        pad,
        width,
        s,
        section_font,
        edge_font,
    )


def _render_matchup_column(
    Image,
    draw,
    canvas,
    *,
    title,
    total,
    lines,
    portraits,
    x,
    y,
    col_w,
    s,
    tokens: LayoutTokens,
    section_font,
    hero_font,
    meta_font,
    value_font,
    accent,
):
    draw.text((x, y), _t(title), font=section_font, fill=accent)
    _draw_matchup_assets(
        Image,
        draw,
        canvas,
        lines,
        portraits,
        x,
        y + 32 * s,
        col_w,
        hero_font,
        meta_font,
        s=s,
        tokens=tokens,
    )


def _render_value_edge(draw, card, y, pad, width, s, section_font, edge_font):
    """Numeric edge + confidence. No decorative meter — the number is the meaning."""

    vc = _t(card.value_change or "Even")
    color = POSITIVE if str(vc).startswith("+") else NEGATIVE if str(vc).startswith("-") else TEXT
    conf = _t(f"{card.confidence} confidence".upper()) if card.confidence else ""
    draw.text((pad, y), vc, font=edge_font, fill=color)
    if conf:
        draw.text((pad, y + 52 * s), conf, font=section_font, fill=MUTED)
        return y + 80 * s
    return y + 52 * s


def _render_single_player(
    Image,
    draw,
    canvas,
    card,
    portraits,
    y,
    pad,
    width,
    s,
    tokens: LayoutTokens,
    hero_font,
    section_font,
    body_font,
    meta_font,
):
    line = card.acquire_lines[0] if card.acquire_lines else share.ShareAssetLine(label="Player")
    portrait = tokens.portrait + 40 * s
    box_h = portrait + 200 * s
    _rounded_rect(draw, (pad, y, width - pad, y + box_h), 18 * s, SURFACE_RAISED)
    box = (pad + 22 * s, y + 56 * s, pad + 22 * s + portrait, y + 56 * s + portrait)
    _paste_portrait(Image, canvas, portraits.get(line.player_id), box)
    tx = pad + 22 * s + portrait + 20 * s
    draw.text((pad + 22 * s, y + 12 * s), (card.title or "PLAYER").upper(), font=section_font, fill=MUTED)
    draw.text((tx, y + 56 * s), line.label, font=hero_font, fill=TEXT)
    cursor = y + 56 * s + _text_height(draw, line.label, hero_font) + 12 * s
    if line.subtitle:
        draw.text((tx, cursor), line.subtitle, font=body_font, fill=MUTED)
        cursor += 40 * s
    metrics = " · ".join(card.metrics)
    if metrics:
        for item in _wrap(draw, metrics, meta_font, width - tx - pad, max_lines=3):
            draw.text((tx, cursor), item, font=meta_font, fill=MUTED)
            cursor += 28 * s
    action = (card.action or "").upper()
    badge_w = max(100 * s, _text_width(draw, action, section_font) + 28 * s)
    _rounded_rect(draw, (tx, cursor + 12 * s, tx + badge_w, cursor + 52 * s), 10 * s, (20, 60, 70))
    draw.text((tx + 14 * s, cursor + 20 * s), action, font=section_font, fill=ACCENT)
    if card.confidence:
        draw.text((tx, cursor + 60 * s), f"{card.confidence} confidence", font=meta_font, fill=MUTED)
        cursor += 40 * s
    return max(y + box_h, cursor + 80 * s)


def _draw_matchup_assets(
    Image,
    draw,
    canvas,
    lines: Iterable[share.ShareAssetLine],
    portraits,
    x,
    y,
    max_w,
    name_font,
    meta_font,
    *,
    s: int = 2,
    tokens: LayoutTokens | None = None,
    portrait: int | None = None,
):
    """Vertical in-column stack: asset / separator / asset. Plus never uses card coordinates."""

    cursor = y
    line_list = list(lines)
    visible = _visible_asset_lines(line_list)
    overflow = max(0, len(line_list) - len(visible))
    if tokens is None:
        tokens = layout_tokens(s, TIER_STANDARD)
        if portrait is not None:
            tokens = LayoutTokens(**{**tokens.__dict__, "portrait": portrait})
    face = min(tokens.portrait, max(48 * s, max_w // 3))
    name_gap = 12 * s
    sep_h = tokens.sep_slot
    for index, line in enumerate(visible):
        if index:
            plus = "+"
            plus_w = _text_width(draw, plus, meta_font)
            plus_x = x + max(0, (max_w - plus_w) // 2)
            plus_h = _text_height(draw, plus, meta_font)
            plus_y = cursor + max(0, (sep_h - plus_h) // 2)
            draw.text((plus_x, plus_y), plus, font=meta_font, fill=ACCENT)
            cursor += sep_h

        is_player = line.kind == "player"
        if is_player:
            _paste_portrait(
                Image,
                canvas,
                portraits.get(line.player_id) if line.player_id else None,
                (x, cursor, x + face, cursor + face),
            )
            tx = x + face + name_gap
            text_w = max(40, max_w - face - name_gap)
            ty = cursor + max(4 * s, (face - tokens.name_line) // 4)
            for name_line in _untruncated_name_lines(draw, line.label, name_font, text_w):
                draw.text((tx, ty), _t(name_line), font=name_font, fill=TEXT)
                ty += tokens.name_line
            if line.subtitle:
                draw.text((tx, ty), _t(line.subtitle), font=meta_font, fill=MUTED)
                ty += tokens.meta_line
            cursor += max(face, ty - cursor) + tokens.asset_gap
            continue

        pick_lines = _untruncated_name_lines(draw, line.label, meta_font, max_w - 24)
        chip_h = max(tokens.pick_chip, tokens.meta_line * len(pick_lines) + 16)
        _rounded_rect(
            draw,
            (x, cursor, x + max_w, cursor + chip_h),
            10,
            SURFACE_RAISED,
        )
        text_y = cursor + max(8, (chip_h - tokens.meta_line * len(pick_lines)) // 2)
        for pick_line in pick_lines:
            draw.text((x + 14, text_y), _t(pick_line), font=meta_font, fill=TEXT)
            text_y += tokens.meta_line
        cursor += chip_h + 8
    if overflow:
        draw.text((x, cursor), f"+{overflow} more", font=meta_font, fill=MUTED)


def _untruncated_name_lines(draw, text: str, font, max_w: int) -> list[str]:
    """Wrap on spaces only. Never ellipsize a player or pick name."""

    lines = _wrap(draw, text or "", font, max_w, max_lines=4)
    return lines or [_t(text) or ""]


def _truncate(draw, text: str, font, max_w: int) -> str:
    if _text_width(draw, text, font) <= max_w:
        return text
    ell = "…"
    for end in range(len(text), 0, -1):
        trial = text[:end].rstrip() + ell
        if _text_width(draw, trial, font) <= max_w:
            return trial
    return ell
