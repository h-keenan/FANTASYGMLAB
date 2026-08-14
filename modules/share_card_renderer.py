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
    return lines[:6]


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


def preview_png_bytes(png: bytes, *, max_width: int = share.PREVIEW_RASTER_WIDTH) -> bytes:
    """Downscale an export PNG for the in-app preview. Share/save still uses `png`."""

    return phone_display_png(png, max_width)


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

    brand_font = _font(ImageFont, 48 * s, bold=True)
    kicker_font = _font(ImageFont, 28 * s, bold=True)
    title_font = _font(ImageFont, 56 * s, bold=True)
    hero_font = _font(ImageFont, 52 * s, bold=True)
    section_font = _font(ImageFont, 32 * s, bold=True)
    body_font = _font(ImageFont, 40 * s)
    meta_font = _font(ImageFont, 28 * s, bold=True)
    footer_font = _font(ImageFont, 28 * s)
    value_font = _font(ImageFont, 52 * s, bold=True)
    edge_font = _font(ImageFont, 64 * s, bold=True)

    pad = 36 * s
    y = 28 * s

    mark_size = 72 * s
    mark_img = _high_res_mark(Image, mark_size)
    if mark_img is not None:
        canvas.paste(mark_img, (pad, y), mark_img)
        text_x = pad + mark_size + 16 * s
    else:
        draw.text((pad, y + 12 * s), brand_identity.PRODUCT_MARK, font=hero_font, fill=ACCENT)
        text_x = pad + _text_width(draw, brand_identity.PRODUCT_MARK, hero_font) + 16 * s
    draw.text((text_x, y + 8 * s), brand_identity.PRODUCT_NAME, font=brand_font, fill=TEXT)
    draw.text((text_x, y + 52 * s), "TRADE RECOMMENDATION" if card.card_type == share.CARD_TYPE_TRADE else "RECOMMENDATION", font=kicker_font, fill=ACCENT)
    y += 108 * s

    rec_title = (card.action or card.title or "Recommendation").upper().replace(" PLUS ", " + ")
    for line in _wrap(draw, rec_title, title_font, width - pad * 2)[:2]:
        draw.text((pad, y), line, font=title_font, fill=TEXT)
        y += 58 * s
    y += 8 * s

    why_lines = _wrap(
        draw,
        card.reason or "See FantasyGM Lab for the full analysis.",
        body_font,
        width - pad * 2,
    )[:3]
    why_h = 36 * s + 44 * s * max(1, len(why_lines)) + 12 * s
    footer_h = 88 * s + 16 * s
    footer_top = height - pad - footer_h
    content_bottom = footer_top - why_h - 20 * s

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
            footer_font,
            edge_font,
            content_bottom=content_bottom,
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
            height,
            s,
            hero_font,
            section_font,
            body_font,
            meta_font,
        )

    y += 16 * s
    draw.text((pad, y), "WHY", font=section_font, fill=MUTED)
    y += 36 * s
    for line in why_lines:
        draw.text((pad, y), line, font=body_font, fill=TEXT)
        y += 44 * s

    _draw_brand_footer(Image, draw, canvas, card, footer_top, width, pad, s, footer_font, brand_font)

    buffer = BytesIO()
    canvas.save(buffer, format="PNG", optimize=True, compress_level=4)
    payload = buffer.getvalue()
    if key:
        share.cache_put(key, payload)
    return payload


def _draw_brand_footer(Image, draw, canvas, card, y, width, pad, s, footer_font, brand_font):
    qr_size = 88 * s
    qr_bytes = share_card_qr.share_qr_png_bytes(box_size=max(4, 3 * s), border=4)
    qr_img = Image.open(BytesIO(qr_bytes)).convert("RGB")
    resample = getattr(getattr(Image, "Resampling", Image), "NEAREST", Image.NEAREST)
    qr_img = qr_img.resize((qr_size, qr_size), resample)
    qr_x = pad
    qr_y = y
    plate = (qr_x - 6 * s, qr_y - 6 * s, qr_x + qr_size + 6 * s, qr_y + qr_size + 6 * s)
    _rounded_rect(draw, plate, 10 * s, (255, 255, 255))
    canvas.paste(qr_img, (qr_x, qr_y))
    copy_x = qr_x + qr_size + 22 * s
    draw.text((copy_x, qr_y + 18 * s), brand_identity.PRODUCT_DOMAIN, font=brand_font, fill=TEXT)
    draw.text((copy_x, qr_y + 68 * s), share_card_qr.QR_LABEL, font=footer_font, fill=MUTED)
    return y + qr_size + 12 * s


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
    footer_font,
    edge_font,
    content_bottom: int | None = None,
):
    gap = 28 * s
    col_w = (width - pad * 2 - gap) // 2
    left_x = pad
    right_x = pad + col_w + gap
    # Keep portraits smaller than the column so the full name can sit underneath
    # at the hero size — never beside the headshot, never ellipsized.
    portrait = min(132 * s, max(96 * s, (col_w - 16 * s) * 2 // 5))
    give_h = _matchup_column_height(card.send_lines, s, portrait=portrait)
    get_h = _matchup_column_height(card.acquire_lines, s, portrait=portrait)
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
        col_w=col_w - 16 * s,
        s=s,
        section_font=section_font,
        hero_font=hero_font,
        meta_font=meta_font,
        value_font=value_font,
        accent=NEGATIVE,
        portrait=portrait,
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
        col_w=col_w - 16 * s,
        s=s,
        section_font=section_font,
        hero_font=hero_font,
        meta_font=meta_font,
        value_font=value_font,
        accent=POSITIVE,
        portrait=portrait,
    )
    y += col_h + 24 * s
    return _render_value_edge(
        draw,
        card,
        y,
        pad,
        width,
        s,
        section_font,
        footer_font,
        edge_font,
        meta_font,
    )


def _matchup_column_height(lines, s, *, portrait: int | None = None) -> int:
    extra = 48 * s
    face = 132 * s if portrait is None else portrait
    visible = list(lines)[:2]
    prev_player = False
    for line in visible:
        is_player = getattr(line, "kind", "player") == "player"
        if is_player:
            extra += face + 12 * s + 52 * s + 32 * s + 12 * s
            prev_player = True
        else:
            if prev_player:
                extra += 44 * s
            extra += 80 * s
            prev_player = False
    return extra


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
    section_font,
    hero_font,
    meta_font,
    value_font,
    accent,
    portrait: int | None = None,
):
    draw.text((x, y), title, font=section_font, fill=accent)
    total_label = share.format_share_value(total) or "—"
    draw.text(
        (x + col_w - _text_width(draw, total_label, value_font), y),
        total_label,
        font=value_font,
        fill=TEXT,
    )
    _draw_matchup_assets(
        Image,
        draw,
        canvas,
        lines,
        portraits,
        x,
        y + 44 * s,
        col_w,
        hero_font,
        meta_font,
        s=s,
        portrait=portrait,
    )


def _render_value_edge(draw, card, y, pad, width, s, section_font, footer_font, edge_font, meta_font):
    vc = card.value_change or "Even"
    color = POSITIVE if str(vc).startswith("+") else NEGATIVE if str(vc).startswith("-") else TEXT
    conf = f"{card.confidence} confidence".upper() if card.confidence else ""
    draw.text((pad, y), vc, font=edge_font, fill=color)
    rest = "VALUE EDGE"
    if conf:
        rest = f"{rest}  ·  {conf}"
    draw.text(
        (pad + _text_width(draw, vc, edge_font) + 16 * s, y + 18 * s),
        rest,
        font=section_font,
        fill=TEXT,
    )
    track_left = pad
    track_right = width - pad
    track_w = track_right - track_left
    track_y = y + 78 * s
    track_h = 18 * s
    _rounded_rect(draw, (track_left, track_y, track_right, track_y + track_h), 9 * s, BAR_TRACK)
    geometry = value_edge_bar_geometry(
        acquire=card.acquire_total,
        send=card.send_total,
        delta=card_value_delta(card),
        max_px=track_w,
    )
    center = track_left + int(geometry["half"])
    draw.rectangle((center - s, track_y - 3 * s, center + s, track_y + track_h + 3 * s), fill=MUTED)
    fill = int(geometry["fill"])
    marker_x = center
    if geometry["direction"] == "receive" and fill:
        right = min(track_right, center + fill)
        _rounded_rect(draw, (center, track_y, right, track_y + track_h), 9 * s, POSITIVE)
        marker_x = right
    elif geometry["direction"] == "send" and fill:
        left = max(track_left, center - fill)
        _rounded_rect(draw, (left, track_y, center, track_y + track_h), 9 * s, NEGATIVE)
        marker_x = left
    r = 8 * s
    draw.ellipse((marker_x - r, track_y + track_h // 2 - r, marker_x + r, track_y + track_h // 2 + r), fill=TEXT)
    return y + 110 * s


def _render_single_player(Image, draw, canvas, card, portraits, y, pad, width, height, s, hero_font, section_font, body_font, meta_font):
    line = card.acquire_lines[0] if card.acquire_lines else share.ShareAssetLine(label="Player")
    why_reserve = 160 * s
    footer_reserve = 160 * s
    box_h = max(420 * s, height - y - why_reserve - footer_reserve)
    _rounded_rect(draw, (pad, y, width - pad, y + box_h), 18 * s, SURFACE_RAISED)
    portrait = 220 * s
    portrait_box = (pad + 22 * s, y + 70 * s, pad + 22 * s + portrait, y + 70 * s + portrait)
    _paste_portrait(Image, canvas, portraits.get(line.player_id), portrait_box)

    tx = pad + 22 * s + portrait + 20 * s
    draw.text((pad + 22 * s, y + 12 * s), (card.title or "PLAYER").upper(), font=section_font, fill=MUTED)
    draw.text((tx, y + 52 * s), line.label, font=hero_font, fill=TEXT)
    if line.subtitle:
        draw.text((tx, y + 110 * s), line.subtitle, font=body_font, fill=MUTED)
    metrics = " · ".join(card.metrics)
    if metrics:
        wrapped = _wrap(draw, metrics, meta_font, width - tx - pad)[:2]
        my = y + 180 * s
        for item in wrapped:
            draw.text((tx, my), item, font=meta_font, fill=MUTED)
            my += 28 * s

    action = (card.action or "").upper()
    badge_w = max(100 * s, _text_width(draw, action, section_font) + 28 * s)
    badge_y = y + 340 * s
    _rounded_rect(draw, (tx, badge_y, tx + badge_w, badge_y + 40 * s), 10 * s, (20, 60, 70))
    draw.text((tx + 14 * s, badge_y + 8 * s), action, font=section_font, fill=ACCENT)
    if card.confidence:
        draw.text((tx, badge_y + 48 * s), f"{card.confidence} confidence", font=meta_font, fill=MUTED)
    return y + box_h + 8 * s


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
    portrait: int | None = None,
):
    """Headshot above the untruncated name; pick packages use a + joiner."""

    cursor = y
    line_list = list(lines)
    visible = line_list[:2]
    overflow = max(0, len(line_list) - len(visible))
    face = min(portrait or 132 * s, max_w)
    prev_was_player = False
    for line in visible:
        is_player = line.kind == "player"
        if is_player:
            face_x = x + max(0, (max_w - face) // 2)
            _paste_portrait(
                Image,
                canvas,
                portraits.get(line.player_id) if line.player_id else None,
                (face_x, cursor, face_x + face, cursor + face),
            )
            cursor += face + 12 * s
            for name_line in _untruncated_name_lines(draw, line.label, name_font, max_w):
                draw.text((x, cursor), name_line, font=name_font, fill=TEXT)
                cursor += 52 * s
            if line.subtitle:
                draw.text((x, cursor), line.subtitle, font=meta_font, fill=MUTED)
                cursor += 32 * s
            cursor += 8 * s
            prev_was_player = True
            continue

        if prev_was_player:
            plus = "+"
            plus_x = x + max(0, (max_w - _text_width(draw, plus, name_font)) // 2)
            draw.text((plus_x, cursor), plus, font=name_font, fill=ACCENT)
            cursor += 44 * s
        chip_h = 72 * s
        _rounded_rect(draw, (x, cursor, x + max_w, cursor + chip_h), 12 * s, SURFACE_RAISED)
        pick_lines = _untruncated_name_lines(draw, line.label, meta_font, max_w - 32 * s)
        text_y = cursor + max(12 * s, (chip_h - 32 * s * len(pick_lines)) // 2)
        for pick_line in pick_lines:
            tw = _text_width(draw, pick_line, meta_font)
            draw.text((x + max(16 * s, (max_w - tw) // 2), text_y), pick_line, font=meta_font, fill=TEXT)
            text_y += 32 * s
        cursor += chip_h + 10 * s
        prev_was_player = False
    if overflow:
        draw.text((x, cursor), f"+{overflow} more", font=meta_font, fill=MUTED)


def _untruncated_name_lines(draw, text: str, font, max_w: int) -> list[str]:
    """Wrap on spaces only. Never ellipsize a player or pick name."""

    lines = _wrap(draw, text or "", font, max_w)
    return lines[:4] or [text or ""]


def _truncate(draw, text: str, font, max_w: int) -> str:
    if _text_width(draw, text, font) <= max_w:
        return text
    ell = "…"
    for end in range(len(text), 0, -1):
        trial = text[:end].rstrip() + ell
        if _text_width(draw, trial, font) <= max_w:
            return trial
    return ell
