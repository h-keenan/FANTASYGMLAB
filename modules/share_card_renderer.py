"""Deterministic Pillow renderer for FantasyGM Lab Share Recommendation cards."""

from __future__ import annotations

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
    candidates = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            ]
        )
    candidates.extend(
        [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_width(draw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return int(box[2] - box[0])


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = (text or "").split()
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
    return lines[:4]


def _rounded_rect(draw, xy, radius: int, fill) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def comparison_bar_widths(acquire: int, send: int, *, max_px: int) -> tuple[int, int]:
    """Proportional bars vs the larger side — tiny gaps stay tiny."""

    peak = max(int(acquire or 0), int(send or 0), 1)
    acquire_px = int(round(max_px * max(0, acquire) / peak))
    send_px = int(round(max_px * max(0, send) / peak))
    if acquire > 0:
        acquire_px = max(acquire_px, 2)
    if send > 0:
        send_px = max(send_px, 2)
    return acquire_px, send_px


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


def _paste_portrait(Image, canvas, raw: bytes | None, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    slot = Image.new("RGB", (w, h), PORTRAIT_BG)
    if raw:
        try:
            portrait = Image.open(BytesIO(raw)).convert("RGB")
            scale = max(w / portrait.width, h / portrait.height)
            nw, nh = int(portrait.width * scale), int(portrait.height * scale)
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
            portrait = portrait.resize((nw, nh), resample)
            left = max(0, (nw - w) // 2)
            top = max(0, (nh - h) // 2)
            portrait = portrait.crop((left, top, left + w, top + h))
            slot.paste(portrait, (0, 0))
        except Exception:
            pass
    else:
        from PIL import ImageDraw as _Draw

        d = _Draw.Draw(slot)
        d.ellipse((w * 0.28, h * 0.18, w * 0.72, h * 0.55), fill=(90, 98, 110))
        d.ellipse((w * 0.18, h * 0.52, w * 0.82, h * 1.15), fill=(90, 98, 110))
    mask = Image.new("L", (w, h), 0)
    from PIL import ImageDraw as _Draw2

    _Draw2.Draw(mask).rounded_rectangle((0, 0, w, h), radius=max(12, w // 8), fill=255)
    canvas.paste(slot, (x0, y0), mask)


def _load_portraits(card: share.ShareRecommendationCard) -> dict[str, bytes | None]:
    out: dict[str, bytes | None] = {}
    for line in list(card.acquire_lines) + list(card.send_lines):
        if line.player_id and line.player_id not in out:
            out[line.player_id] = share.fetch_portrait_bytes(line.player_id)
    return out


def _cache_key(card: share.ShareRecommendationCard, width: int, height: int) -> str:
    return f"{card.fingerprint}:{RENDER_VERSION}:{width}x{height}:{share_card_qr.RENDER_VERSION}"


def render_share_card_png(
    card: share.ShareRecommendationCard,
    *,
    width: int = share.SHARE_WIDTH,
    height: int = share.SHARE_HEIGHT,
    portraits: dict[str, bytes | None] | None = None,
) -> bytes:
    """Render a share PNG. Uses cache when fingerprint matches."""

    if not card.is_shareable:
        raise ValueError(card.decline_reason or "Recommendation is not shareable.")

    key = _cache_key(card, width, height) if card.fingerprint else ""
    cached = share.cache_get(key) if key else None
    if cached:
        return cached

    Image, ImageDraw, ImageFont = _require_pillow()
    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    portraits = portraits if portraits is not None else _load_portraits(card)
    s = max(1, int(round(width / 1080)))

    title_font = _font(ImageFont, 14 * s, bold=True)
    hero_font = _font(ImageFont, 28 * s, bold=True)
    section_font = _font(ImageFont, 13 * s, bold=True)
    body_font = _font(ImageFont, 16 * s)
    meta_font = _font(ImageFont, 13 * s)
    footer_font = _font(ImageFont, 12 * s)
    value_font = _font(ImageFont, 22 * s, bold=True)

    pad = 28 * s
    y = 24 * s

    for color, inset, lift in (
        ((34, 211, 238), 0, 0),
        ((250, 204, 21), 9 * s, 5 * s),
        ((239, 68, 68), 18 * s, 10 * s),
    ):
        x0, y0 = width - pad - 80 * s + inset, 18 * s + lift
        x1, y1 = width - pad - 10 * s + inset // 2, 55 * s + lift
        draw.arc((x0, y0, x1, y1), start=220, end=320, fill=color, width=max(2, s))

    mark_size = 40 * s
    mark_img = _high_res_mark(Image, mark_size)
    if mark_img is not None:
        canvas.paste(mark_img, (pad, y), mark_img)
        text_x = pad + mark_size + 8 * s
    else:
        draw.text((pad, y + 4 * s), brand_identity.PRODUCT_MARK, font=title_font, fill=ACCENT)
        text_x = pad + _text_width(draw, brand_identity.PRODUCT_MARK, title_font) + 8 * s
    draw.text((text_x, y + 4 * s), brand_identity.PRODUCT_NAME, font=meta_font, fill=TEXT)
    y += 32 * s
    draw.text((pad, y), card.title.upper(), font=section_font, fill=MUTED)
    y += 22 * s

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
            hero_font,
            section_font,
            body_font,
            meta_font,
            value_font,
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
            hero_font,
            section_font,
            body_font,
            meta_font,
        )

    y += 10 * s
    why_h = 88 * s
    _rounded_rect(draw, (pad, y, width - pad, y + why_h), 10 * s, SURFACE)
    draw.text((pad + 14 * s, y + 10 * s), "WHY", font=section_font, fill=MUTED)
    why_lines = _wrap(
        draw,
        card.reason or "See FantasyGM Lab for the full analysis.",
        body_font,
        width - pad * 2 - 28 * s,
    )
    ty = y + 28 * s
    for line in why_lines:
        draw.text((pad + 14 * s, ty), line, font=body_font, fill=TEXT)
        ty += 18 * s

    _draw_brand_footer(Image, draw, canvas, card, width, height, pad, s, footer_font, meta_font)

    buffer = BytesIO()
    canvas.save(buffer, format="PNG", optimize=True, compress_level=6)
    payload = buffer.getvalue()
    if key:
        share.cache_put(key, payload)
    return payload


def _draw_brand_footer(Image, draw, canvas, card, width, height, pad, s, footer_font, meta_font):
    qr_size = 72 * s
    footer_top = height - qr_size - 28 * s
    draw.line((pad, footer_top - 10 * s, width - pad, footer_top - 10 * s), fill=BORDER, width=max(1, s))
    qr_bytes = share_card_qr.share_qr_png_bytes(box_size=max(4, 3 * s), border=4)
    qr_img = Image.open(BytesIO(qr_bytes)).convert("RGB")
    resample = getattr(getattr(Image, "Resampling", Image), "NEAREST", Image.NEAREST)
    qr_img = qr_img.resize((qr_size, qr_size), resample)
    qr_x = width - pad - qr_size
    qr_y = footer_top
    # White quiet-zone plate so the QR stays high-contrast on the dark card.
    plate = (qr_x - 4 * s, qr_y - 4 * s, qr_x + qr_size + 4 * s, qr_y + qr_size + 4 * s)
    _rounded_rect(draw, plate, 6 * s, (255, 255, 255))
    canvas.paste(qr_img, (qr_x, qr_y))

    copy_x = pad
    draw.text((copy_x, footer_top + 8 * s), card.brand_footer or brand_identity.PRODUCT_NAME, font=meta_font, fill=TEXT)
    draw.text((copy_x, footer_top + 26 * s), share_card_qr.QR_LABEL, font=footer_font, fill=MUTED)
    draw.text((copy_x, footer_top + 44 * s), brand_identity.PRODUCT_DOMAIN, font=footer_font, fill=ACCENT)


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
    hero_font,
    section_font,
    body_font,
    meta_font,
    value_font,
):
    inner_w = width - pad * 2
    if card.action:
        badge = (card.action or "").upper()
        badge_w = max(120 * s, _text_width(draw, badge, section_font) + 24 * s)
        _rounded_rect(draw, (pad, y, pad + badge_w, y + 28 * s), 8 * s, (20, 60, 70))
        draw.text((pad + 12 * s, y + 6 * s), badge, font=section_font, fill=ACCENT)
        y += 36 * s

    y = _render_trade_side(
        Image,
        draw,
        canvas,
        title="ACQUIRER / RECEIVES",
        total=card.acquire_total,
        lines=card.acquire_lines,
        portraits=portraits,
        y=y,
        pad=pad,
        width=width,
        s=s,
        section_font=section_font,
        body_font=body_font,
        meta_font=meta_font,
        value_font=value_font,
        bar_color=POSITIVE,
        bar_width=comparison_bar_widths(
            int(card.acquire_total or 0),
            int(card.send_total or 0),
            max_px=inner_w,
        )[0],
        bar_max=inner_w,
    )
    y += 10 * s
    y = _render_trade_side(
        Image,
        draw,
        canvas,
        title="SENDER / SENDS",
        total=card.send_total,
        lines=card.send_lines,
        portraits=portraits,
        y=y,
        pad=pad,
        width=width,
        s=s,
        section_font=section_font,
        body_font=body_font,
        meta_font=meta_font,
        value_font=value_font,
        bar_color=NEGATIVE,
        bar_width=comparison_bar_widths(
            int(card.acquire_total or 0),
            int(card.send_total or 0),
            max_px=inner_w,
        )[1],
        bar_max=inner_w,
    )
    y += 8 * s
    _rounded_rect(draw, (pad, y, width - pad, y + 70 * s), 10 * s, SURFACE)
    draw.text((pad + 14 * s, y + 10 * s), "VALUE EDGE", font=section_font, fill=MUTED)
    vc = card.value_change or "Even"
    color = POSITIVE if str(vc).startswith("+") else NEGATIVE if str(vc).startswith("-") else TEXT
    draw.text((pad + 14 * s, y + 28 * s), vc, font=hero_font, fill=color)
    if card.confidence:
        conf = f"{card.confidence} confidence"
        draw.text(
            (width - pad - 14 * s - _text_width(draw, conf, body_font), y + 34 * s),
            conf,
            font=body_font,
            fill=TEXT,
        )
    return y + 78 * s


def _render_trade_side(
    Image,
    draw,
    canvas,
    *,
    title,
    total,
    lines,
    portraits,
    y,
    pad,
    width,
    s,
    section_font,
    body_font,
    meta_font,
    value_font,
    bar_color,
    bar_width,
    bar_max,
):
    box_h = 150 * s
    _rounded_rect(draw, (pad, y, width - pad, y + box_h), 12 * s, SURFACE_RAISED)
    draw.text((pad + 14 * s, y + 10 * s), title, font=section_font, fill=MUTED)
    total_label = share.format_share_value(total) or "—"
    draw.text(
        (width - pad - 14 * s - _text_width(draw, total_label, value_font), y + 8 * s),
        total_label,
        font=value_font,
        fill=TEXT,
    )
    track_y = y + 36 * s
    track_h = 10 * s
    _rounded_rect(draw, (pad + 14 * s, track_y, pad + 14 * s + bar_max, track_y + track_h), 4 * s, BAR_TRACK)
    if bar_width > 0:
        _rounded_rect(
            draw,
            (pad + 14 * s, track_y, pad + 14 * s + bar_width, track_y + track_h),
            4 * s,
            bar_color,
        )
    _draw_asset_stack(
        Image,
        draw,
        canvas,
        lines,
        portraits,
        pad + 14 * s,
        y + 54 * s,
        width - pad * 2 - 28 * s,
        body_font,
        meta_font,
        compact=True,
        s=s,
    )
    return y + box_h


def _render_single_player(Image, draw, canvas, card, portraits, y, pad, width, s, hero_font, section_font, body_font, meta_font):
    line = card.acquire_lines[0] if card.acquire_lines else share.ShareAssetLine(label="Player")
    box_h = 210 * s
    _rounded_rect(draw, (pad, y, width - pad, y + box_h), 12 * s, SURFACE_RAISED)
    portrait = 96 * s
    portrait_box = (pad + 18 * s, y + 18 * s, pad + 18 * s + portrait, y + 18 * s + portrait)
    _paste_portrait(Image, canvas, portraits.get(line.player_id), portrait_box)

    tx = pad + 18 * s + portrait + 16 * s
    draw.text((tx, y + 22 * s), line.label, font=hero_font, fill=TEXT)
    if line.subtitle:
        draw.text((tx, y + 56 * s), line.subtitle, font=body_font, fill=MUTED)
    metrics = " · ".join(card.metrics)
    if metrics:
        draw.text((tx, y + 80 * s), metrics, font=meta_font, fill=MUTED)

    action = (card.action or "").upper()
    badge_w = max(80 * s, _text_width(draw, action, section_font) + 24 * s)
    _rounded_rect(draw, (tx, y + 110 * s, tx + badge_w, y + 138 * s), 8 * s, (20, 60, 70))
    draw.text((tx + 12 * s, y + 116 * s), action, font=section_font, fill=ACCENT)
    if card.confidence:
        draw.text((tx, y + 150 * s), f"{card.confidence} confidence", font=meta_font, fill=MUTED)
    return y + box_h + 8 * s


def _draw_asset_stack(
    Image,
    draw,
    canvas,
    lines: Iterable[share.ShareAssetLine],
    portraits,
    x,
    y,
    max_w,
    body_font,
    meta_font,
    *,
    compact: bool = False,
    s: int = 2,
):
    cursor = y
    line_list = list(lines)
    max_visible = 3 if compact else (6 if len(line_list) > 4 else 4)
    visible = line_list[:max_visible]
    overflow = max(0, len(line_list) - len(visible))
    portrait = 28 * s if compact else (36 * s if max_visible > 4 else 48 * s)
    for line in visible:
        if line.kind == "player" and line.player_id:
            box = (x, cursor, x + portrait, cursor + portrait)
            _paste_portrait(Image, canvas, portraits.get(line.player_id), box)
            text_x = x + portrait + 8 * s
            draw.text(
                (text_x, cursor + 2 * s),
                _truncate(draw, line.label, body_font, max_w - portrait - 8 * s),
                font=body_font,
                fill=TEXT,
            )
            if line.subtitle:
                draw.text((text_x, cursor + 16 * s), line.subtitle, font=meta_font, fill=MUTED)
            cursor += portrait + 6 * s
        else:
            draw.text((x, cursor), _truncate(draw, line.label, body_font, max_w), font=body_font, fill=TEXT)
            if line.subtitle:
                draw.text((x, cursor + 16 * s), line.subtitle, font=meta_font, fill=MUTED)
            cursor += 28 * s
    if overflow:
        draw.text((x, cursor), _truncate(draw, f"+{overflow} more", body_font, max_w), font=meta_font, fill=MUTED)


def _truncate(draw, text: str, font, max_w: int) -> str:
    if _text_width(draw, text, font) <= max_w:
        return text
    ell = "…"
    for end in range(len(text), 0, -1):
        trial = text[:end].rstrip() + ell
        if _text_width(draw, trial, font) <= max_w:
            return trial
    return ell
